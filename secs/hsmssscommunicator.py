import threading
import secs


class HsmsSsCommunicatorError(secs.SecsCommunicatorError):

    def __init__(self, msg):
        super(HsmsSsCommunicatorError, self).__init__(msg)


class HsmsSsSendMessageError(secs.SecsSendMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsSendMessageError, self).__init__(msg, ref_msg)


class HsmsSsWaitReplyMessageError(secs.SecsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsWaitReplyMessageError, self).__init__(msg, ref_msg)


class HsmsSsTimeoutT3Error(HsmsSsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsTimeoutT3Error, self).__init__(msg, ref_msg)


class HsmsSsTimeoutT6Error(HsmsSsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsTimeoutT6Error, self).__init__(msg, ref_msg)


class HsmsSsRejectMessageError(HsmsSsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsRejectMessageError, self).__init__(msg, ref_msg)


class HsmsSsCommunicateState:

    NOT_CONNECT = 'not_connect'
    CONNECTED = 'connected'
    SELECTED = 'selected'


class SendReplyHsmsSsMessagePack:

    def __init__(self, msg):
        self.__msg = msg
        self.__reply_msg_cdt = threading.Condition()
        self.__reply_msg = None
        self.__terminated = False

    def shutdown(self):
        with self.__reply_msg_cdt:
            self.__terminated = True
            self.__reply_msg_cdt.notify_all()

    def __is_terminated(self):
        with self.__reply_msg_cdt:
            return self.__terminated

    def get_system_bytes(self):
        return self.__msg.system_bytes

    def put_reply_msg(self, reply_msg):
        with self.__reply_msg_cdt:
            self.__reply_msg = reply_msg
            self.__reply_msg_cdt.notify_all()

    def wait_reply_msg(self, timeout):

        with self.__reply_msg_cdt:

            if self.__is_terminated():
                return None

            if self.__reply_msg is not None:
                return self.__reply_msg

            self.__reply_msg_cdt.wait(timeout)
        
            return self.__reply_msg


class SendReplyHsmsSsMessagePackPool:

    def __init__(self):
        self.__pool = dict()
        self.__lock = threading.Lock()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.shutdown()
    
    def shutdown(self):
        with self.__lock:
            for pack in self.__pool.values():
                pack.shutdown()

    def entry(self, pack):
        with self.__lock:
            self.__pool[pack.get_system_bytes()] = pack

    def remove(self, pack):
        with self.__lock:
            del self.__pool[pack.get_system_bytes()]

    def put_reply_msg(self, reply_msg):
        with self.__lock:
            key = reply_msg.system_bytes
            if key in self.__pool:
                self.__pool[key].put_reply_msg(reply_msg)
                return True
            else:
                return False


class HsmsSsConnection:
    
    def __init__(
            self, sock, comm,
            recv_primary_msg_put_callback,
            recv_all_msg_put_callback,
            sended_msg_put_callback,
            error_put_callback):

        self.__sock = sock
        self.__comm = comm
        self.__put_recv_primary_msg = recv_primary_msg_put_callback
        self.__put_recv_all_msg = recv_all_msg_put_callback
        self.__put_sended_msg = sended_msg_put_callback
        self.__put_error = error_put_callback

        self.__terminated_cdt = threading.Condition()
        self.__terminated = False

        self.__bbqq = secs.WaitingQueuing()

        self.__send_reply_pool = SendReplyHsmsSsMessagePackPool()

        self.__send_lock = threading.Lock()

        threading.Thread(target=self.__receiving_socket_bytes, daemon=True).start()
        threading.Thread(target=self.__reading_msg, daemon=True).start()
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.shutdown()

    def shutdown(self):
        with self.__terminated_cdt:

            if not self.__is_terminated():

                self.__terminated = True

                self.__bbqq.shutdown()
                self.__send_reply_pool.shutdown()

                self.__terminated_cdt.notify_all()

    def __is_terminated(self):
        with self.__terminated_cdt:
            return self.__terminated
    
    def await_termination(self, timeout=None):
        with self.__terminated_cdt:
            self.__terminated_cdt.wait_for(self.__is_terminated, timeout)

    def __receiving_socket_bytes(self):
        try:
            while not self.__is_terminated():
                bs = self.__sock.recv(4096)
                if bs:
                    self.__bbqq.puts(bs)
                else:
                    raise HsmsSsCommunicatorError("Terminate detect")

        except HsmsSsCommunicatorError as e:
            if not self.__is_terminated():
                self.__put_error(e)
        except Exception as e:
            if not self.__is_terminated():
                self.__put_error(HsmsSsCommunicatorError(e))

        finally:
            self.shutdown()

    def __reading_msg(self):
        try:
            while not self.__is_terminated():

                heads = list()
                pos = 0
                size = 14

                r = self.__bbqq.put_to_list(heads, pos, size)
                if r < 0:
                    return

                pos += r

                while pos < size:
                    r = self.__bbqq.put_to_list(
                        heads, pos, size,
                        self.__comm.timeout_t8)
                    
                    if r < 0:
                        raise HsmsSsCommunicatorError("T8-Timeout")
                    else:
                        pos += r

                bodys = list()
                pos = 0
                size = (heads[0] << 24
                        | heads[1] << 16
                        | heads[2] << 8
                        | heads[3]) - 10

                while pos < size:
                    r = self.__bbqq.put_to_list(
                        bodys, pos, size,
                        self.__comm.timeout_t8)
                    
                    if r < 0:
                        raise HsmsSsCommunicatorError("T8-Timeout")
                    else:
                        pos += r

                msg = secs.HsmsSsMessage.from_bytes(bytes(heads) + bytes(bodys))

                self.__put_recv_all_msg(msg)

                if not self.__send_reply_pool.put_reply_msg(msg):
                    self.__put_recv_primary_msg(msg, self)

        except Exception as e:
            if not self.__is_terminated():
                self.__put_error(e)

        finally:
            self.shutdown()

    def send(self, msg):

        timeout_tx = -1.0

        ctrl_type = msg.get_control_type()

        if ctrl_type == secs.HsmsSsControlType.DATA:
            if msg.wbit:
                timeout_tx = self.__comm.timeout_t3

        elif (ctrl_type == secs.HsmsSsControlType.SELECT_REQ
              or ctrl_type == secs.HsmsSsControlType.LINKTEST_REQ):

            timeout_tx = self.__comm.timeout_t6

        def _send():
            with self.__send_lock:
                try:
                    self.__sock.sendall(msg.to_bytes())
                    self.__put_sended_msg(msg)
                except Exception as e:
                    raise HsmsSsSendMessageError(e, msg)
        
        if timeout_tx >= 0.0:

            pack = SendReplyHsmsSsMessagePack(msg)

            try:
                self.__send_reply_pool.entry(pack)

                _send()

                rsp = pack.wait_reply_msg(timeout_tx)

                if rsp is None:

                    if self.__is_terminated():

                        raise HsmsSsCommunicatorError("HsmsSsConnection terminated")
                    
                    else:

                        if ctrl_type == secs.HsmsSsControlType.DATA:

                            raise HsmsSsTimeoutT3Error("HsmsSs-Timeout-T3", msg)

                        else:
                            self.shutdown()
                            raise HsmsSsTimeoutT6Error("HsmsSs-Timeout-T6", msg)

                else:

                    if rsp.get_control_type() == secs.HsmsSsControlType.REJECT_REQ:

                        raise HsmsSsRejectMessageError("HsmsSs-Reject-Message", msg)

                    else:
                        return rsp

            finally:
                self.__send_reply_pool.remove(pack)
            
        else:
            _send()
            return None


class AbstractHsmsSsCommunicator(secs.AbstractSecsCommunicator):

    def __init__(self, session_id, is_equip, **kwargs):
        super(AbstractHsmsSsCommunicator, self).__init__(session_id, is_equip, **kwargs)

        self._hsmsss_connection = None
        self._hsmsss_connection_lock = threading.Lock()

        self._hsmsss_comm = HsmsSsCommunicateState.NOT_CONNECT
        self._hsmsss_comm_lock = threading.Lock()
        self._hsmsss_comm_lstnrs = list()

        self.__recv_all_msg_putter = secs.CallbackQueuing(self._put_recv_all_msg)
        self.__sended_msg_putter = secs.CallbackQueuing(self._put_sended_msg)
        self.__error_putter = secs.CallbackQueuing(super()._put_error)

        hsmsss_comm_lstnr = kwargs.get('hsmsss_communicate', None)
        if hsmsss_comm_lstnr is not None:
            self.add_hsmsss_communicate_listener(hsmsss_comm_lstnr)

    def __str__(self):
        ipaddr = self._get_ipaddress()
        return str({
            'protocol': self._get_protocol(),
            'ip_address': (ipaddr[0]) + ':' + str(ipaddr[1]),
            'session_id': self.session_id,
            'is_equip': self.is_equip,
            'communicate_state': self.get_hsmsss_communicate_state(),
            'name': self.name
        })

    def __repr__(self):
        return repr({
            'protocol': self._get_protocol(),
            'ip_address': self._get_ipaddress(),
            'session_id': self.session_id,
            'is_equip': self.is_equip,
            'communicate_state': self.get_hsmsss_communicate_state(),
            'name': self.name
        })

    def _get_protocol(self):
        # prototype
        raise NotImplementedError()
    
    def _get_ipaddress(self):
        # prototype
        raise NotImplementedError()

    @property
    def session_id(self):
        pass

    @session_id.setter
    def session_id(self, val):
        """SESSION-ID setter.

        Args:
            val (int): SESSION_ID
        """
        self.device_id = val

    @session_id.getter
    def session_id(self):
        """SESSION-ID getter.

        Returns:
            int: SESSION_ID
        """
        return self.device_id

    def _put_error(self, e):
        self.__error_putter.put(e)

    def _open(self):
        with self._open_close_rlock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")

        self._set_opened()
    
    def _close(self):
        with self._open_close_rlock:
            if self.is_closed:
                return
        
        self._set_closed()

        self.__recv_all_msg_putter.shutdown()
        self.__sended_msg_putter.shutdown()
        self.__error_putter.shutdown()
    
    def _build_hsmsss_connection(self, sock, recv_primary_msg_callback):
        return HsmsSsConnection(
            sock,
            self,
            recv_primary_msg_callback,
            self.__recv_all_msg_putter.put,
            self.__sended_msg_putter.put,
            self.__error_putter.put)

    def _set_hsmsss_connection(self, conn, callback=None):
        with self._hsmsss_connection_lock:
            if self._hsmsss_connection is None:
                self._hsmsss_connection = conn
                if callback is not None:
                    callback()
                return True
            else:
                return False

    def _unset_hsmsss_connection(self, callback=None):
        with self._hsmsss_connection_lock:
            if self._hsmsss_connection is not None:
                self._hsmsss_connection = None
                if callback is not None:
                    callback()

    def _send(self, strm, func, wbit, secs2body, system_bytes, device_id):
        return self.send_hsmsss_msg(
            secs.HsmsSsDataMessage(strm, func, wbit, secs2body, system_bytes, device_id))

    def send_hsmsss_msg(self, msg):
        def _f():
            with self._hsmsss_connection_lock:
                if self._hsmsss_connection is None:
                    raise HsmsSsSendMessageError("HsmsSsCommunicator not connected", msg)
                else:
                    return self._hsmsss_connection
        
        return _f().send(msg)

    def build_select_req(self):
        return secs.HsmsSsControlMessage.build_select_request(
            self._create_system_bytes())

    @staticmethod
    def build_select_rsp(primary, status):
        return secs.HsmsSsControlMessage.build_select_response(
            primary,
            status)

    def build_linktest_req(self):
        return secs.HsmsSsControlMessage.build_linktest_request(
            self._create_system_bytes())

    @staticmethod
    def build_linktest_rsp(primary):
        return secs.HsmsSsControlMessage.build_linktest_response(primary)

    @staticmethod
    def build_reject_req(primary, reason):
        return secs.HsmsSsControlMessage.build_reject_request(primary, reason)

    def build_separate_req(self):
        return secs.HsmsSsControlMessage.build_separate_request(
            self._create_system_bytes())

    def send_select_req(self):
        msg = self.build_select_req()
        return self.send_hsmsss_msg(msg)

    def send_select_rsp(self, primary, status):
        msg = self.build_select_rsp(primary, status)
        return self.send_hsmsss_msg(msg)

    def send_linktest_req(self):
        msg = self.build_linktest_req()
        return self.send_hsmsss_msg(msg)

    def send_linktest_rsp(self, primary):
        msg = self.build_linktest_rsp(primary)
        return self.send_hsmsss_msg(msg)

    def send_reject_req(self, primary, reason):
        msg = self.build_reject_req(primary, reason)
        return self.send_hsmsss_msg(msg)

    def send_separate_req(self):
        msg = self.build_separate_req()
        return self.send_hsmsss_msg(msg)

    def get_hsmsss_communicate_state(self):
        with self._hsmsss_comm_lock:
            return self._hsmsss_comm
        
    def add_hsmsss_communicate_listener(self, listener):
        """Add HSMS-SS-Communicate-state-change-listener.

        If listener-arguments is 1, put HSMS-SS-Communicate-State.
        If listener-arguments is 2, put HSMS-SS-Communicate-State and self-communicator-instance.
        HSMS-SS-Communicate-State is instance of `secs.HsmsSsCommunicateState`.
        self-communicator-instance is instance of `secs.AbstractSecsCommunicator`.

        Args:
            listener (function): HSMS-SS-Communicate-state-change-listener

        Returns:
            None
        """
        with self._hsmsss_comm_lock:
            self._hsmsss_comm_lstnrs.append(listener)
            listener(self._hsmsss_comm, self)

    def remove_hsmsss_communicate_listener(self, listener):
        """Remove HSMS-SS-Communicate-state-change-listener.

        Args:
            listener (function): HSMS-SS-Communicate-state-change-listener

        Returns:
            None
        """
        with self._hsmsss_comm_lock:
            self._hsmsss_comm_lstnrs.remove(listener)

    def _put_hsmsss_comm_state(self, state, callback=None):
        with self._hsmsss_comm_lock:
            if state != self._hsmsss_comm:
                self._hsmsss_comm = state
                for ls in self._hsmsss_comm_lstnrs:
                    if self._is_single_args_listener(ls):
                        ls(self._hsmsss_comm)
                    else:
                        ls(self._hsmsss_comm, self)
                self._put_communicated(state == HsmsSsCommunicateState.SELECTED)
                if callback is not None:
                    callback()

    def _put_hsmsss_comm_state_to_not_connected(self, callback=None):
        self._put_hsmsss_comm_state(
            HsmsSsCommunicateState.NOT_CONNECT,
            callback)

    def _put_hsmsss_comm_state_to_connected(self, callback=None):
        self._put_hsmsss_comm_state(
            HsmsSsCommunicateState.CONNECTED,
            callback)

    def _put_hsmsss_comm_state_to_selected(self, callback=None):
        self._put_hsmsss_comm_state(
            HsmsSsCommunicateState.SELECTED,
            callback)
