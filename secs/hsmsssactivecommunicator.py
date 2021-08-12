import concurrent.futures
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

        self.__recv_primary_msg_putter = secs.CallbackQueuing(super()._put_recv_primary_msg)

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

                with self._build_hsmsss_connection(self, sock, self.__receiving_msg) as conn:

                    try:
                        pass

                    finally:
                        self._unset_hsmsss_connection(self._put_hsmsss_comm_state_to_not_connected)

                        try:
                            sock.shutdown(socket.SHUT_RDWR)
                        except Exception:
                            pass

                    # TODO

                    pass
        
        except ConnectionError as e:
            self._put_error(secs.HsmsSsCommunicatorError(e))
        except secs.HsmsSsCommunicatorError as e:
            self._put_error(e)
        except secs.HsmsSsSendMessageError as e:
            self._put_error(e)
        except secs.HsmsSsWaitReplyError as e:
            self._put_error(e)
    
    def __receiving_msg(self, recv_msg, conn):

        if recv_msg is None:
            with self.__circuit_cdt:
                self.__circuit_cdt.notify_all()
                return

        ctrl_type = recv_msg.get_control_type()

        try:
            if ctrl_type == secs.HsmsSsControlType.DATA:

                if self.get_hsmsss_communicate_state() == secs.HsmsSsCommunicateState.SELECTED:
                    self._put_recv_primary_msg(recv_msg)
                else:
                    self.send_reject_req(recv_msg, secs.HsmsSsRejectReason.NOT_SELECTED)

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


    def _open2(self):

        def _f():

            with secs.CallbackQueuing(self._put_recv_primary_msg) as pq:

                while self.is_open:

                    try:

                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

                            sock.connect(self._get_ipaddress())

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

    def _put_recv_primary_msg(self, recv_msg):
        self.__recv_primary_msg_putter.put(recv_msg)
