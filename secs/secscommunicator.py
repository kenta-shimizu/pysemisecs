import threading
import secs


class SecsCommunicatorError(Exception):

    def __init__(self, msg):
        super(SecsCommunicatorError, self).__init__(msg)


class SecsSendMessageError(Exception):

    def __init__(self, msg, ref_msg):
        super(SecsSendMessageError, self).__init__(msg)
        self._ref_msg = ref_msg

    def get_reference_message(self):
        return self._ref_msg


class SecsWaitReplyError(Exception):
    
    def __init__(self, msg, ref_msg):
        super(SecsWaitReplyError, self).__init__(msg)
        self._ref_msg = ref_msg

    def get_reference_message(self):
        return self._ref_msg


class AbstractQueuing:

    def __init__(self):
        self._v_lock = threading.Lock()
        self._v_cdt = threading.Condition()
        self._vv = list()
        self._opened = False
        self._closed = False
        self._open_close_lock = threading.Lock()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def open(self):
        with self._open_close_lock:
            if self._closed:
                raise RuntimeError("Already closed")
            if self._opened:
                raise RuntimeError("Already opened")
            self._opened = True

    def close(self):
        with self._open_close_lock:
            if self._closed:
                return
            self._closed = True
        with self._v_cdt:
            self._v_cdt.notify_all()

    def put(self, value):
        if value:
            with self._v_lock:
                self._vv.append(value)
                with self._v_cdt:
                    self._v_cdt.notify_all()

    def puts(self, values):
        if values:
            with self._v_lock:
                self._vv.extend([v for v in values])
                with self._v_cdt:
                    self._v_cdt.notify_all()

    def _poll_vv(self):
        with self._v_lock:
            if self._vv:
                return self._vv.pop(0)
            else:
                return None


class CallbackQueuing(AbstractQueuing):

    def __init__(self, func):
        super(CallbackQueuing, self).__init__()
        self._func = func

    def open(self):
        super().open()

        def _f():
            while True:
                v = self._poll_vv()
                if v is None:
                    with self._v_cdt:
                        self._v_cdt.wait()
                        with self._open_close_lock:
                            if self._closed:
                                self._func(None)
                                return
                else:
                    self._func(v)

        threading.Thread(target=_f, daemon=True).start()


class PutListQueuing(AbstractQueuing):

    def __init__(self):
        super(PutListQueuing, self).__init__()

    def put_to_list(self, values, pos, size, timeout=None):

        def _f(vv, p, m):
            with self._v_lock:
                vvsize = len(self._vv)
                if vvsize > 0:
                    r = m - p
                    if vvsize > r:
                        vv.extend(self._vv[0:r])
                        del self._vv[0:r]
                        return r
                    else:
                        vv.extend(self._vv)
                        self._vv.clear()
                        return vvsize
                else:
                    return -1

        with self._open_close_lock:
            if self._closed or not self._opened:
                return -1
                
        with self._v_cdt:
            r = _f(values, pos, size)
            if r > 0:
                return r
            self._v_cdt.wait(timeout)

        with self._open_close_lock:
            if self._closed or not self._opened:
                return -1

        return _f(values, pos, size)


class WaitingQueuing(AbstractQueuing):

    def __init__(self):
        super(WaitingQueuing, self).__init__()

    def poll(self, timeout=None):

        with self._open_close_lock:
            if self._closed or not self._opened:
                return None

        with self._v_cdt:
            v = self._poll_vv()
            if v is not None:
                return v
            self._v_cdt.wait(timeout)

        with self._open_close_lock:
            if self._closed or not self._opened:
                return None

        return self._poll_vv()


class AbstractSecsCommunicator:

    _DEFAULT_TIMEOUT_T1 =  1.0
    _DEFAULT_TIMEOUT_T2 = 15.0
    _DEFAULT_TIMEOUT_T3 = 45.0
    _DEFAULT_TIMEOUT_T4 = 45.0
    _DEFAULT_TIMEOUT_T5 = 10.0
    _DEFAULT_TIMEOUT_T6 =  5.0
    _DEFAULT_TIMEOUT_T7 = 10.0
    _DEFAULT_TIMEOUT_T8 =  6.0

    def __init__(self, device_id, is_equip, **kwargs):
        self._dev_id = device_id
        self._is_equip = is_equip

        self.set_name(kwargs.get('name', None))

        self.set_timeout_t1(kwargs.get('timeout_t1', self._DEFAULT_TIMEOUT_T1))
        self.set_timeout_t2(kwargs.get('timeout_t2', self._DEFAULT_TIMEOUT_T2))
        self.set_timeout_t3(kwargs.get('timeout_t3', self._DEFAULT_TIMEOUT_T3))
        self.set_timeout_t4(kwargs.get('timeout_t4', self._DEFAULT_TIMEOUT_T4))
        self.set_timeout_t5(kwargs.get('timeout_t5', self._DEFAULT_TIMEOUT_T5))
        self.set_timeout_t6(kwargs.get('timeout_t6', self._DEFAULT_TIMEOUT_T6))
        self.set_timeout_t7(kwargs.get('timeout_t7', self._DEFAULT_TIMEOUT_T7))
        self.set_timeout_t8(kwargs.get('timeout_t8', self._DEFAULT_TIMEOUT_T8))

        self._sys_num = 0

        self._communicating = False
        self._comm_rlock = threading.RLock()
        self._comm_condition = threading.Condition()

        self._recv_primary_msg_lstnrs = list()
        self._recv_all_msg_lstnrs = list()
        self._sended_msg_lstnrs = list()
        self._communicated_lstnrs = list()
        self._error_listeners = list()

        rpm = kwargs.get('recv_primary_msg', None)
        if rpm is not None:
            self.add_recv_primary_msg_listener(rpm)

        # TODO
        # kwargs

        self._opened = False
        self._closed = False
        self._open_close_rlock = threading.RLock()

    def open(self):
        """Open communicator
        """
        self._open()

    def _open(self):
        # prototype-pattern
        raise NotImplementedError()

    def close(self):
        """Close communicator
        """
        self._close()

    def _close(self):
        # prototype-pattern
        raise NotImplementedError()

    def open_and_wait_until_communicating(self):

        if not self.is_open():
            self._open()

        while True:
            if self.is_closed():
                raise SecsCommunicatorError("Communicator closed")
            if self.is_communicating():
                return
            with self._comm_condition:
                self._comm_condition.wait()

    def is_open(self):
        with self._open_close_rlock:
            return self._opened and not self._closed

    def is_closed(self):
        with self._open_close_rlock:
            return self._closed

    def _set_opened(self):
        with self._open_close_rlock:
            self._opened = True

    def _set_closed(self):
        with self._open_close_rlock:
            self._closed = True
            with self._comm_condition:
                self._comm_condition.notify_all()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._close()

    def send(self, strm, func, wbit, secs2body=None):
        """Send primary message

        Args:
            strm (int): Stream-Number.
            func (int): Function-Number.
            wbit (bool): W-Bit.
            secs2body (<Secs2Body> tuple or list, optional): SECS-II-body. Defaults to None.

        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.
            SecsWaitReplyError: if reply not received.

        Returns:
            <SecsMessage> or None: Reply-Message if exist, otherwise None.

        Examples:
            if send 'S1F1 W.',
            send(1, 1, True)

            if send  
            'S5F1 W
            <L
              <B  0x01>
              <U2 1001>
              <A  "ON FIRE">
            >.',
            send(
                5, 1, True,
                ('L', [
                    ('B', [0x01]),
                    ('U2', [1001]),
                    ('A', "ON FIRE")
                ])
                )
        """
        return self._send(
            strm, func, wbit,
            self._create_secs2body(secs2body),
            self._create_system_bytes(),
            self._dev_id)

    def send_sml(self, sml_str):
        """Send primary message by SML

        Args:
            sml_str (str): SML-string.

        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.
            SecsWaitReplyError: if reply not received.
            Secs2BodySmlParseError: if Secs2body parse failed.
            SmlParseError: if SML parse failed.

        Returns:
            SecsMessage or None: Reply-Message if exist, otherwise None.
        """
        strm, func, wbit, s2b = secs.SmlParser.parse(sml_str)
        return self.send(strm, func, wbit, s2b)

    def reply(self, primary, strm, func, wbit, secs2body=None):
        """Send reply message

        Args:
            primary (SecsMessage): Primary-Message.
            strm (int): Stream-Number.
            func (int): Function-Number.
            wbit (bool: W-Bit.
            Secs2Body (Secs2Body or tuple, list, optional): SECS-II-body. Defaults to None.

        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.

        Returns:
            None: None

        Examples:
            if reply 'S1F18 <B 0x0>.',
            reply(2, 18, False, ('B', [0x0]))
        """
        return self._send(
            strm, func, wbit,
            self._create_secs2body(secs2body),
            primary.get_system_bytes(),
            self._dev_id)

    def reply_sml(self, primary, sml_str):
        """Send reply message by SML

        Args:
            primary (SecsMessage): Primary-Message
            sml_str (str): SML-String
            
        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.
            Secs2BodySmlParseError: if Secs2body parse failed.
            SmlParseError: if SML parse failed.

        Returns:
            None: None
        """
        strm, func, wbit, s2b = secs.SmlParser.parse(sml_str)
        return self.reply(
            primary,
            strm, func, wbit,
            self._create_secs2body(s2b))

    def _create_system_bytes(self):
        self._sys_num = (self._sys_num + 1) & 0xFFFF
        n = self._sys_num
        d = self._dev_id if self._is_equip else 0
        return bytes([
            (d >> 8) & 0x7F,
            d & 0xFF,
            (n >> 8) & 0xFF,
            n & 0xFF
        ])

    @staticmethod
    def _create_secs2body(v):
        if v is None:
            return None
        elif isinstance(v, secs.AbstractSecs2Body):
            return v
        else:
            tt = type(v)
            if (tt is list or tt is tuple) and len(v) == 2:
                return secs.Secs2BodyBuilder.build(v[0], v[1])
            else:
                raise TypeError('Secs2Body is tuple or list, and length == 2')
        

    def _send(self, strm, func, wbit, secs2body, system_bytes, device_id):
        """prototype-pattern send

        Args:
            strm (int): Stream-Number.
            func (int): Function-Number.
            wbit (bool): W-Bit.
            secs2body (Secs2Body, tuple, list or None): SECS-II-body.
            system_bytes (bytes): System-4-bytes.
            device_id (int): Device-ID.

        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.
            SecsWaitReplyError: if reply not received.

        Returns:
            SecsMessage or None: Reply-Message if exist, otherwise None
        """
        raise NotImplementedError()

    def set_name(self, name):
        """Communicator-Name setter

        Args:
            name (str): Communicator-Name
        """
        self._comm_name = None if name is None else str(name)
    
    def get_name(self):
        """Communicator-Name getter

        Returns:
            str or None: str if setted, otherwise None.
        """
        return self._comm_name

    @staticmethod
    def _tstx(v):
        """test-set-timeout-tx

        Args:
            v (int or float): timeout-time-seconds.

        Raises:
            TypeError: raise if v is None.
            ValueError: raise if v is not greater than 0.0.

        Returns:
            int or float: tested value
        """
        if v is None:
            raise TypeError("Timeout-value require not None")
        if v > 0.0:
            return v
        else:
            raise ValueError("Timeout-value require > 0.0")

    def set_timeout_t1(self, v):
        """Timeout-T1 setter.

        Args:
            v (int or float): Timeout-T1 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self._timeout_t1 = self._tstx(v)

    def set_timeout_t2(self, v):
        """Timeout-T2 setter.

        Args:
            v (int or float): Timeout-T2 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self._timeout_t2 = self._tstx(v)

    def set_timeout_t3(self, v):
        """Timeout-T3 setter.

        Args:
            v (int or float): Timeout-T3 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self._timeout_t3 = self._tstx(v)

    def set_timeout_t4(self, v):
        """Timeout-T4 setter.

        Args:
            v (int or float): Timeout-T4 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self._timeout_t4 = self._tstx(v)

    def set_timeout_t5(self, v):
        """Timeout-T5 setter.

        Args:
            v (int or float): Timeout-T5 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self._timeout_t5 = self._tstx(v)

    def set_timeout_t6(self, v):
        """Timeout-T6 setter.

        Args:
            v (int or float): Timeout-T6 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self._timeout_t6 = self._tstx(v)

    def set_timeout_t7(self, v):
        """Timeout-T7 setter.

        Args:
            v (int or float): Timeout-T7 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self._timeout_t7 = self._tstx(v)

    def set_timeout_t8(self, v):
        """Timeout-T8 setter.

        Args:
            v (int or float): Timeout-T8 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self._timeout_t8 = self._tstx(v)

    def add_recv_primary_msg_listener(self, l):
        self._recv_primary_msg_lstnrs.append(l)

    def remove_recv_priary_msg_listener(self, l):
        self._recv_primary_msg_lstnrs.remove(l)

    def _put_recv_primary_msg(self, recv_msg):
        if recv_msg is not None:
            for lstnr in self._recv_primary_msg_lstnrs:
                lstnr(self, recv_msg)

    def add_recv_all_msg_listener(self, l):
        self._recv_all_msg_lstnrs.append(l)

    def remove_recv_all_msg_listener(self, l):
        self._recv_all_msg_lstnrs.remove(l)
    
    def _put_recv_all_msg(self, recv_msg):
        if recv_msg is not None:
            for lstnr in self._recv_all_msg_lstnrs:
                lstnr(self, recv_msg)
    
    def add_sended_msg_listener(self, l):
        self._sended_msg_lstnrs.append(l)

    def remove_sended_msg_listener(self, l):
        self._sended_msg_lstnrs.remove(l)

    def _put_sended_msg(self, sended_msg):
        if sended_msg is not None:
            for lstnr in self._sended_msg_lstnrs:
                lstnr(self, sended_msg)
    
    def add_communicated_listener(self, l):
        with self._comm_rlock:
            self._communicated_lstnrs.append(l)
            l(self, self._communicating)

    def remove_communicated_listener(self, l):
        with self._comm_rlock:
            self._communicated_lstnrs.remove(l)

    def _put_communicated(self, communicating):
        with self._comm_rlock:
            if communicating != self._communicating:
                self._communicating = communicating
                for lstnr in self._communicated_lstnrs:
                    lstnr(self, self._communicating)
                with self._comm_condition:
                    self._comm_condition.notify_all()

    def is_communicating(self):
        with self._comm_rlock:
            return self._communicating
    
    def add_error_listener(self, l):
        self._error_listeners.append(l)

    def remove_error_listener(self, l):
        self._error_listeners.remove(l)

    def _put_error(self, e):
        for lstnr in self._error_listeners:
            lstnr(self, e)
