import concurrent.futures
import threading
import socket
import secs


class HsmsSsActiveCommunicator(secs.AbstractHsmsSsCommunicator):

    __PROTOCOL_NAME = 'HSMS-SS-ACTIVE'

    def __init__(self, ip_address, port, session_id, is_equip, **kwargs):
        """[summary]

        How to

        Args:
            ip_address ([type]): [description]
            port ([type]): [description]
            session_id ([type]): [description]
            is_equip (bool): [description]
        """

        super(HsmsSsActiveCommunicator, self).__init__(session_id, is_equip, **kwargs)

        self.__tpe = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        self.__ipaddr = (ip_address, port)

        self.__waiting_cdt = threading.Condition()
        self.__open_close_local_lock = threading.Lock()

    def get_protocol(self):
        return self.__PROTOCOL_NAME

    def get_ipaddress(self):
        return self.__ipaddr

    def _open(self):

        with self.__open_close_local_lock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")
            self._set_opened()

        def _f():

            with secs.CallbackQueuing(self._put_recv_primary_msg) as pq:

                while self.is_open:

                    try:

                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

                            sock.connect(self.get_ipaddress())

                            def _recv(msg):

                                if msg is None:
                                    with self.__waiting_cdt:
                                        self.__waiting_cdt.notify_all()
                                    return

                                ctrl_type = msg.get_control_type()

                                try:
                                    if ctrl_type == secs.HsmsSsControlType.DATA:

                                        if self.get_hsmsss_communicate_state() == secs.HsmsSsCommunicateState.SELECTED:
                                            pq.put(msg)
                                        else:
                                            self.send_reject_req(msg, secs.HsmsSsRejectReason.NOT_SELECTED)

                                    elif ctrl_type == secs.HsmsSsControlType.LINKTEST_REQ:

                                        self.send_linktest_rsp(msg)

                                    elif ctrl_type == secs.HsmsSsControlType.SEPARATE_REQ:

                                        with self.__waiting_cdt:
                                            self.__waiting_cdt.notify_all()

                                    elif ctrl_type == secs.HsmsSsControlType.SELECT_REQ:
                                        self.send_reject_req(msg, secs.HsmsSsRejectReason.NOT_SUPPORT_TYPE_S)

                                    elif (ctrl_type == secs.HsmsSsControlType.SELECT_RSP
                                        or ctrl_type == secs.HsmsSsControlType.LINKTEST_RSP):

                                        self.send_reject_req(msg, secs.HsmsSsRejectReason.TRANSACTION_NOT_OPEN)

                                    elif ctrl_type == secs.HsmsSsControlType.REJECT_REQ:

                                        # Nothing
                                        pass

                                    else:

                                        if secs.HsmsSsControlType.has_s_type(msg.get_s_type()):
                                            self.send_reject_req(msg, secs.HsmsSsRejectReason.NOT_SUPPORT_TYPE_P)
                                        else:
                                            self.send_reject_req(msg, secs.HsmsSsRejectReason.NOT_SUPPORT_TYPE_S)
                                        
                                except secs.HsmsSsCommunicatorError as e:
                                    self._put_error(e)
                                except secs.HsmsSsSendMessageError as e:
                                    self._put_error(e)

                            with secs.HsmsSsConnection(sock, self, _recv) as conn:

                                try:
                                    self._put_hsmsss_comm_state_to_connected()

                                    rsp = conn.send(self.build_select_req())

                                    if rsp is not None:

                                        if rsp.get_control_type() == secs.HsmsSsControlType.SELECT_RSP:

                                            ss = rsp.get_select_status()

                                            if (ss == secs.HsmsSsSelectStatus.SUCCESS
                                                or ss == secs.HsmsSsSelectStatus.ACTIVED):

                                                self._set_hsmsss_connection(
                                                    conn,
                                                    self._put_hsmsss_comm_state_to_selected)

                                                with self.__waiting_cdt:
                                                    self.__waiting_cdt.wait()

                                finally:
                                    self._unset_hsmsss_connection(self._put_hsmsss_comm_state_to_not_connected)

                                    try:
                                        sock.shutdown(socket.SHUT_RDWR)
                                    except Exception:
                                        pass

                    except ConnectionError as e:
                        self._put_error(secs.HsmsSsCommunicatorError(e))
                    except secs.HsmsSsCommunicatorError as e:
                        self._put_error(e)
                    except secs.HsmsSsSendMessageError as e:
                        self._put_error(e)
                    except secs.HsmsSsWaitReplyError as e:
                        self._put_error(e)
                    finally:
                        self._put_hsmsss_comm_state_to_not_connected()

                    if self.is_closed:
                        return None

                    with self.__waiting_cdt:
                        self.__waiting_cdt.wait(self.timeout_t5)

        self.__tpe.submit(_f)

    def _close(self):

        with self.__open_close_local_lock:
            if self.is_closed:
                return
            self._set_closed()

        with self.__waiting_cdt:
            self.__waiting_cdt.notify_all()

        self.__tpe.shutdown(wait=True, cancel_futures=True)
