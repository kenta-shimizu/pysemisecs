import threading
import socket
import secs


class HsmsSsPassiveCommunicator(secs.AbstractHsmsSsCommunicator):

    __PROTOCOL = 'HSMS-SS-PASSIVE'
    __TIMEOUT_REBIND = 5.0

    def __init__(self, ip_address, port, session_id, is_equip, **kwargs):
        super(HsmsSsPassiveCommunicator, self).__init__(session_id, is_equip, **kwargs)
        
        self.__ipaddr = (ip_address, port)

        self.__cdts = list()
        self.__ths = list()

        self.timeout_rebind = kwargs.get('timeout_rebind', self.__TIMEOUT_REBIND)

    def _get_protocol(self):
        return self.__PROTOCOL

    def _get_ipaddress(self):
        return self.__ipaddr
    
    @property
    def timeout_rebind(self):
        pass

    @timeout_rebind.setter
    def timeout_rebind(self, val):
        self.__timeout_rebind = float(val)
    
    @timeout_rebind.getter
    def timeout_rebind(self):
        return self.__timeout_rebind

    def _open(self):

        with self._open_close_rlock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")

            th = threading.Thread(target=self.__loop, daemon=True)
            self.__ths.append(th)
            th.start()

            super()._open()

            self._set_opened()
    
    def __loop(self):
        cdt = threading.Condition()
        try:
            self.__cdts.append(cdt)
            while not self.is_closed:
                self.__open_server()
                if self.is_closed:
                    return
                with cdt:
                    cdt.wait(self.timeout_rebind)
        finally:
            self.__cdts.remove(cdt)
    
    def __open_server(self):
        cdt = threading.Condition()
        try:
            self.__cdts.append(cdt)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

                server.bind(self._get_ipaddress())
                server.listen()

                def _f():
                    try:
                        while not self.is_closed:
                            sock = (server.accept())[0]
                            self.__accept_socket(sock)

                    except Exception as e:
                        if not self.is_closed:
                            self._put_error(secs.HsmsSsCommunicatorError(e))
                    finally:
                        with cdt:
                            cdt.notify_all()
                
                th = threading.Thread(target=_f, daemon=True)

                try:
                    self.__ths.append(th)
                    th.start()

                    with cdt:
                        cdt.wait()

                finally:
                    self.__ths.remove(th)

        except Exception as e:
            if not self.is_closed:
                self._put_error(secs.HsmsSsCommunicatorError(e))
        
        finally:
            self.__cdts.remove(cdt)
    
    def __accept_socket(self, sock):
        
        def _f():
            with sock:
                try:
                    # TODO
                    
                    pass

                finally:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except Exception:
                        pass

        threading.Thread(target=_f, daemon=True).start()
    

    def _accept_socket2(self, sock):

        with secs.CallbackQueuing(self._put_recv_primary_msg) as pq, \
                secs.WaitingQueuing() as wq, \
                secs.HsmsSsConnection(sock, self, wq.put) as conn:

            cdt = threading.Condition()

            def _f():

                try:

                    while self.is_open:

                        msg = wq.poll(self.timeout_t7)

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
                    if self.is_open:
                        self._put_error(e)
                except secs.HsmsSsSendMessageError as e:
                    self._put_error(e)
                finally:
                    with cdt:
                        cdt.notify_all()

            self.__tpe.submit(_f)

            try:
                self.__waiting_cdts.append(cdt)
                with cdt:
                    cdt.wait()
            finally:
                self.__waiting_cdts.remove(cdt)

                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass

                sock.close()

            return None


    def _close(self):

        if self.is_closed:
            return

        super()._close()

        self._set_closed()

        for cdt in self.__cdts:
            with cdt:
                cdt.notify_all()

        for th in self.__ths:
            th.join(0.1)
