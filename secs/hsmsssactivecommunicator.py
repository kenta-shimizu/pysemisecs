import threading
import socket
import secs


class HsmsSsActiveCommunicator(secs.AbstractHsmsSsCommunicator):

    __PROTOCOL = 'HSMS-SS-ACTIVE'

    def __init__(self, ip_address, port, session_id, is_equip, **kwargs):
        super(HsmsSsActiveCommunicator, self).__init__(session_id, is_equip, **kwargs)

        self.__ipaddr = (ip_address, port)

        self.__circuit_cdt = threading.Condition()

        self.__cdts = list()
        self.__cdts.append(self.__circuit_cdt)

        self.__ths = list()

        self.__recv_primary_msg_putter = secs.CallbackQueuing(self._put_recv_primary_msg)

    def _get_protocol(self):
        return self.__PROTOCOL

    def _get_ipaddress(self):
        return self.__ipaddr

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
                self.__connect()
                if self.is_closed:
                    return
                with cdt:
                    cdt.wait(self.timeout_t5)
        finally:
            self.__cdts.remove(cdt)

    def __connect(self):

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

                sock.connect(self._get_ipaddress())

                with self._build_hsmsss_connection(sock, self.__receiving_msg) as conn:

                    def _f():
                        conn.await_termination()
                        with self.__circuit_cdt:
                            self.__circuit_cdt.notify_all()
                    
                    th = threading.Thread(target=_f, daemon=True)

                    try:
                        self.__ths.append(th)
                        th.start()

                        self._put_hsmsss_comm_state_to_connected()

                        rsp = conn.send(self.build_select_req())

                        if rsp is not None:

                            ss = rsp.get_select_status()

                            if (ss == secs.HsmsSsSelectStatus.SUCCESS
                                    or ss == secs.HsmsSsSelectStatus.ACTIVED):

                                self._set_hsmsss_connection(
                                    conn,
                                    self._put_hsmsss_comm_state_to_selected)
                                
                                with self.__circuit_cdt:
                                    self.__circuit_cdt.wait()
                                
                    finally:
                        self._unset_hsmsss_connection(
                            self._put_hsmsss_comm_state_to_not_connected)

                        self.__ths.remove(th)

                        try:
                            sock.shutdown(socket.SHUT_RDWR)
                        except Exception as e:
                            if not self.is_closed:
                                self._put_error(e)

        except ConnectionError as e:
            if not self.is_closed:
                self._put_error(secs.HsmsSsCommunicatorError(e))
        except secs.HsmsSsCommunicatorError as e:
            if not self.is_closed:
                self._put_error(e)
        except secs.HsmsSsSendMessageError as e:
            if not self.is_closed:
                self._put_error(e)
        except secs.HsmsSsWaitReplyMessageError as e:
            if not self.is_closed:
                self._put_error(e)
    
    def __receiving_msg(self, recv_msg, conn):

        def _f():

            if recv_msg is None:
                with self.__circuit_cdt:
                    self.__circuit_cdt.notify_all()
                    return

            ctrl_type = recv_msg.get_control_type()

            try:
                if ctrl_type == secs.HsmsSsControlType.DATA:

                    if self.get_hsmsss_communicate_state() == secs.HsmsSsCommunicateState.SELECTED:

                        self.__recv_primary_msg_putter.put(recv_msg)

                    else:
                        conn.send(
                            self.build_select_rsp(
                                recv_msg,
                                secs.HsmsSsRejectReason.NOT_SELECTED))

                elif ctrl_type == secs.HsmsSsControlType.LINKTEST_REQ:

                    conn.send(self.build_linktest_rsp(recv_msg))

                elif ctrl_type == secs.HsmsSsControlType.SEPARATE_REQ:

                    with self.__circuit_cdt:
                        self.__circuit_cdt.notify_all()

                elif ctrl_type == secs.HsmsSsControlType.SELECT_REQ:

                    conn.send(
                        self.build_reject_req(
                            recv_msg,
                            secs.HsmsSsRejectReason.NOT_SUPPORT_TYPE_S))

                elif (ctrl_type == secs.HsmsSsControlType.SELECT_RSP
                      or ctrl_type == secs.HsmsSsControlType.LINKTEST_RSP):

                    conn.send(
                        self.build_reject_req(
                            recv_msg,
                            secs.HsmsSsRejectReason.TRANSACTION_NOT_OPEN))

                elif ctrl_type == secs.HsmsSsControlType.REJECT_REQ:

                    # Nothing
                    pass

                else:

                    if secs.HsmsSsControlType.has_s_type(recv_msg.get_s_type()):

                        conn.send(
                            self.build_reject_req(
                                recv_msg,
                                secs.HsmsSsRejectReason.NOT_SUPPORT_TYPE_P))

                    else:

                        conn.send(
                            self.build_reject_req(
                                recv_msg,
                                secs.HsmsSsRejectReason.NOT_SUPPORT_TYPE_S))
                    
            except secs.HsmsSsSendMessageError as e:
                self._put_error(e)
            except secs.HsmsSsWaitReplyMessageError as e:
                self._put_error(e)
            except secs.HsmsSsCommunicatorError as e:
                self._put_error(e)

        th = threading.Thread(target=_f, daemon=True)
        try:
            self.__ths.append(th)
            th.start()
        finally:
            self.__ths.remove(th)
    
    def _close(self):

        if self.is_closed:
            return

        super()._close()

        self._set_closed()

        self.__recv_primary_msg_putter.shutdown()

        for cdt in self.__cdts:
            with cdt:
                cdt.notify_all()

        for th in self.__ths:
            th.join(0.1)
