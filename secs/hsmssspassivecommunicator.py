import concurrent.futures
import threading
import socket
import secs


class HsmsSsPassiveCommunicator(secs.AbstractHsmsSsCommunicator):

    _PROTOCOL_NAME = 'HSMS-SS-PASSIVE'

    def __init__(self, ip_address, port, session_id, is_equip, **kwargs):
        super(HsmsSsPassiveCommunicator, self).__init__(session_id, is_equip, **kwargs)
        self._tpe = concurrent.futures.ThreadPoolExecutor(max_workers=64)
        self._ipaddr = (ip_address, port)
        self._waiting_cdts = list()

    def get_protocol(self):
        return self._PROTOCOL_NAME

    def get_ipaddress(self):
        return self._ipaddr

    def _open(self):

        with self._open_close_rlock:
            if self.is_closed():
                raise RuntimeError("Already closed")
            if self.is_open():
                raise RuntimeError("Already opened")
            self._set_opened()

        def _open_server():

            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

                    server.bind(self.get_ipaddress())
                    server.listen()
                    
                    cdt = threading.Condition()

                    def _f():
                        try:
                            while not self.is_closed():

                                sock = (server.accept())[0]

                                def _ff():
                                    self._accept_socket(sock)
                                
                                self._tpe.submit(_ff)

                        except Exception as e:
                            if self.is_open():
                                self._put_error(secs.HsmsSsCommunicatorError(e))

                    self._tpe.submit(_f)
                    
                    self._waiting_cdts.append(cdt)
                    with cdt:
                        cdt.wait()

            except Exception as e:
                if self.is_open():
                    self._put_error(secs.HsmsSsCommunicatorError(e))
                    
        self._tpe.submit(_open_server)

    def _accept_socket(self, sock):

        with (
            secs.CallbackQueuing(self._put_recv_primary_msg) as pq,
            secs.WaitingQueuing() as wq,
            secs.HsmsSsConnection(sock, self, wq.put) as conn):

            cdt = threading.Condition()

            def _f():

                try:

                    while self.is_open():

                        msg = wq.poll(self._timeout_t7)

                        if msg is None:
                            raise secs.HsmsSsCommunicatorError("T7-Timeout")

                        ctrl_type = msg.get_control_type()

                        if ctrl_type == secs.HsmsSsControlType.SELECT_REQ:

                            if self._set_hsmsss_connection(conn):

                                conn.send(secs.HsmsSsControlMessage.build_select_response(
                                    msg,
                                    secs.HsmsSsSelectStatus.SUCCESS))

                                break

                            else:

                                conn.send(secs.HsmsSsControlMessage.build_select_response(
                                    msg,
                                    secs.HsmsSsSelectStatus.ALREADY_USED))

                        elif ctrl_type == secs.HsmsSsControlType.LINKTEST_REQ:

                            conn.send(secs.HsmsSsControlMessage.build_linktest_response(msg))

                        elif ctrl_type == secs.HsmsSsControlType.DATA:

                            conn.send(secs.HsmsSsControlMessage.build_reject_request(
                                msg,
                                secs.HsmsSsRejectReason.NOT_SELECTED))

                        elif ctrl_type == secs.HsmsSsControlType.SEPARATE_REQ:

                            return None

                        elif (ctrl_type == secs.HsmsSsControlType.SELECT_RSP
                            or ctrl_type == secs.HsmsSsControlType.LINKTEST_RSP):

                            conn.send(secs.HsmsSsControlMessage.build_reject_request(
                                msg,
                                secs.HsmsSsRejectReason.TRANSACTION_NOT_OPEN))

                        elif ctrl_type == secs.HsmsSsControlType.REJECT_REQ:

                            #Nothing
                            pass

                        else:

                            if secs.HsmsSsControlType.has_s_type(msg.get_s_type()):

                                conn.send(secs.HsmsSsControlMessage.build_reject_request(
                                    msg,
                                    secs.HsmsSsRejectReason.NOT_SUPPORT_TYPE_P))

                            else:

                                conn.send(secs.HsmsSsControlMessage.build_reject_request(
                                    msg,
                                    secs.HsmsSsRejectReason.NOT_SUPPORT_TYPE_S))

                    try:
                        self._put_hsmsss_comm_state_to_selected()

                        while True:

                            msg = wq.poll()

                            if msg is None:
                                raise secs.HsmsSsCommunicatorError("Terminate detect")

                            ctrl_type = msg.get_control_type()

                            if ctrl_type == secs.HsmsSsControlType.DATA:

                                pq.put(msg)

                            elif ctrl_type == secs.HsmsSsControlType.LINKTEST_REQ:

                                self.send_linktest_rsp(msg)

                            elif ctrl_type == secs.HsmsSsControlType.SELECT_REQ:

                                self.send_select_rsp(msg, secs.HsmsSsSelectStatus.ACTIVED)

                            elif ctrl_type == secs.HsmsSsControlType.SEPARATE_REQ:

                                return None

                            elif (ctrl_type == secs.HsmsSsControlType.SELECT_RSP
                                or ctrl_type == secs.HsmsSsControlType.LINKTEST_RSP):

                                self.send_reject_req(msg, secs.HsmsSsRejectReason.TRANSACTION_NOT_OPEN)

                            elif ctrl_type == secs.HsmsSsControlType.REJECT_REQ:

                                #Nothing
                                pass

                            else:

                                if secs.HsmsSsControlType.has_s_type(msg.get_s_type()):
                                    self.send_reject_req(msg, secs.HsmsSsRejectReason.NOT_SUPPORT_TYPE_P)
                                else:
                                    self.send_reject_req(msg, secs.HsmsSsRejectReason.NOT_SUPPORT_TYPE_S)

                    finally:
                        self._unset_hsmsss_connection(self._put_hsmsss_comm_state_to_not_connected)

                except secs.HsmsSsCommunicatorError as e:
                    if self.is_open():
                        self._put_error(e)
                except secs.HsmsSsSendMessageError as e:
                    self._put_error(e)
                finally:
                    with cdt:
                        cdt.notify_all()

            self._tpe.submit(_f)

            try:
                self._waiting_cdts.append(cdt)
                with cdt:
                    cdt.wait()
            finally:
                self._waiting_cdts.remove(cdt)

                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass

                sock.close()

            return None

    def _close(self):

        with self._open_close_rlock:
            if self.is_closed():
                return
            self._set_closed()

        for cdt in self._waiting_cdts:
            with cdt:
                cdt.notify_all()

        self._tpe.shutdown(wait=True, cancel_futures=True)
