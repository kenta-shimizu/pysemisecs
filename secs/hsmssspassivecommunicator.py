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

        self.__recv_primary_msg_putter = secs.CallbackQueuing(self._put_recv_primary_msg)
        
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

                    def _f_sock(sock):
                        with sock:
                            try:
                                self.__accept_socket(sock)
                            except Exception as e:
                                self._put_error(e)
                            finally:
                                try:
                                    sock.shutdown(socket.SHUT_RDWR)
                                except Exception:
                                    pass
                    
                    try:
                        while not self.is_closed:
                            sock = (server.accept())[0]

                            threading.Thread(
                                target=_f_sock,
                                args=(sock, ),
                                daemon=True
                                ).start()

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
        
        qq = secs.WaitingQueuing()

        cdt = threading.Condition()

        try:
            self.__cdts.append(cdt)

            def _put_to_qq(recv_msg, conn):
                qq.put((recv_msg, conn))
            
            with self._build_hsmsss_connection(sock, _put_to_qq) as conn:

                def _comm():
                    conn.await_termination()
                    with cdt:
                        cdt.notify_all()
                
                def _receiving():

                    if self.__receiving_msg_until_selected(qq):

                        try:
                            self.__receiving_msg(qq)
                        finally:
                            self._unset_hsmsss_connection(
                                self._put_hsmsss_comm_state_to_not_connected)

                    with cdt:
                        cdt.notify_all()
                
                threading.Thread(target=_comm, daemon=True).start()
                threading.Thread(target=_receiving, daemon=True).start()

                with cdt:
                    cdt.wait()

        finally:
            self.__cdts.remove(cdt)
            qq.shutdown()

    def __receiving_msg_until_selected(self, qq):

        while not self.is_closed:

            tt = qq.poll(self.timeout_t7)

            if tt is None:
                return False
            
            recv_msg = tt[0]
            conn = tt[1]

            ctrl_type = recv_msg.get_control_type()

            try:
                if ctrl_type == secs.HsmsSsControlType.DATA:

                    conn.send(
                        self.build_select_rsp(
                            recv_msg,
                            secs.HsmsSsRejectReason.NOT_SELECTED))

                elif ctrl_type == secs.HsmsSsControlType.LINKTEST_REQ:

                    conn.send(self.build_linktest_rsp(recv_msg))

                elif ctrl_type == secs.HsmsSsControlType.SEPARATE_REQ:

                    return False

                elif ctrl_type == secs.HsmsSsControlType.SELECT_REQ:

                    r = self._set_hsmsss_connection(
                        conn,
                        self._put_hsmsss_comm_state_to_selected)
                    
                    if r:

                        conn.send(
                            self.build_select_rsp(
                                recv_msg,
                                secs.HsmsSsSelectStatus.SUCCESS))
                        
                        return True

                    else:

                        conn.send(
                            self.build_select_rsp(
                                recv_msg,
                                secs.HsmsSsSelectStatus.ALREADY_USED))
                                
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

        return False

    def __receiving_msg(self, qq):

        while not self.is_closed:

            tt = qq.poll()

            if tt is None:
                return False
            
            recv_msg = tt[0]
            conn = tt[1]

            ctrl_type = recv_msg.get_control_type()

            try:
                if ctrl_type == secs.HsmsSsControlType.DATA:

                    self.__recv_primary_msg_putter.put(recv_msg)

                elif ctrl_type == secs.HsmsSsControlType.LINKTEST_REQ:

                    conn.send(self.build_linktest_rsp(recv_msg))

                elif ctrl_type == secs.HsmsSsControlType.SEPARATE_REQ:

                    return False

                elif ctrl_type == secs.HsmsSsControlType.SELECT_REQ:
                    
                    conn.send(
                        self.build_select_rsp(
                            recv_msg,
                            secs.HsmsSsSelectStatus.ACTIVED))

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

        return False

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
