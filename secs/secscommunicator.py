import threading
import secs


class SecsCommunicatorError(Exception):

    def __init__(self, msg):
        super(SecsCommunicatorError, self).__init__(msg)

    def __str__(self):
        return repr(self)


class SecsWithReferenceMessageError(SecsCommunicatorError):

    def __init__(self, msg, ref_msg):
        super(SecsWithReferenceMessageError, self).__init__(msg)
        self._msg = msg
        self._ref_msg = ref_msg

    def get_reference_message(self):
        return self._ref_msg

    def __str__(self):
        return (self.__class__.__name__ + '('
        + repr(self._msg) + ','
        + self._ref_msg._header10bytes_str()
        + ')')

    def __repr__(self):
        return (self.__class__.__name__ + '('
        + repr(self._msg) + ','
        + repr(self._ref_msg._header10bytes())
        + ')')


class SecsSendMessageError(SecsWithReferenceMessageError):

    def __init__(self, msg, ref_msg):
        super(SecsSendMessageError, self).__init__(msg, ref_msg)


class SecsWaitReplyMessageError(SecsWithReferenceMessageError):
    
    def __init__(self, msg, ref_msg):
        super(SecsWaitReplyMessageError, self).__init__(msg, ref_msg)


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

    __DEFAULT_TIMEOUT_T1 =  1.0
    __DEFAULT_TIMEOUT_T2 = 15.0
    __DEFAULT_TIMEOUT_T3 = 45.0
    __DEFAULT_TIMEOUT_T4 = 45.0
    __DEFAULT_TIMEOUT_T5 = 10.0
    __DEFAULT_TIMEOUT_T6 =  5.0
    __DEFAULT_TIMEOUT_T7 = 10.0
    __DEFAULT_TIMEOUT_T8 =  6.0

    def __init__(self, device_id, is_equip, **kwargs):

        self.__gem = secs.Gem(self)

        self.device_id = device_id
        self.is_equip = is_equip

        self.name = kwargs.get('name', None)
        self.timeout_t1 = kwargs.get('timeout_t1', self.__DEFAULT_TIMEOUT_T1)
        self.timeout_t2 = kwargs.get('timeout_t2', self.__DEFAULT_TIMEOUT_T2)
        self.timeout_t3 = kwargs.get('timeout_t3', self.__DEFAULT_TIMEOUT_T3)
        self.timeout_t4 = kwargs.get('timeout_t4', self.__DEFAULT_TIMEOUT_T4)
        self.timeout_t5 = kwargs.get('timeout_t5', self.__DEFAULT_TIMEOUT_T5)
        self.timeout_t6 = kwargs.get('timeout_t6', self.__DEFAULT_TIMEOUT_T6)
        self.timeout_t7 = kwargs.get('timeout_t7', self.__DEFAULT_TIMEOUT_T7)
        self.timeout_t8 = kwargs.get('timeout_t8', self.__DEFAULT_TIMEOUT_T8)

        gem_mdln = kwargs.get('gem_mdln', None)
        if gem_mdln is not None:
            self.gem.mdln = gem_mdln

        gem_softrev = kwargs.get('gem_softrev', None)
        if gem_softrev is not None:
            self.gem.softrev = gem_softrev

        gem_clock_type = kwargs.get('gem_clock_type', None)
        if gem_clock_type is not None:
            self.gem.clock_type = gem_clock_type

        self._sys_num = 0

        self.__communicating = False
        self.__comm_rlock = threading.RLock()
        self.__comm_condition = threading.Condition()

        self.__recv_primary_msg_lstnrs = list()
        self.__communicate_lstnrs = list()
        self.__error_listeners = list()
        self.__recv_all_msg_lstnrs = list()
        self.__sended_msg_lstnrs = list()

        rpml = kwargs.get('recv_primary_msg', None)
        if rpml is not None:
            self.add_recv_primary_msg_listener(rpml)

        errl = kwargs.get('error', None)
        if errl is not None:
            self.add_error_listener(errl)

        comml = kwargs.get('communicate', None)
        if comml is not None:
            self.add_communicate_listener(comml)
        
        self.__opened = False
        self.__closed = False
        self.__open_close_rlock = threading.RLock()

    @property
    def gem(self):
        pass

    @gem.getter
    def gem(self):
        """GEM getter

        Returns:
            <Gem>: GEM-instance
        """
        return self.__gem

    @property
    def device_id(self):
        pass

    @device_id.getter
    def device_id(self):
        """Device-ID getter.

        Returns:
            int: Device-ID
        """
        return self.__device_id

    @device_id.setter
    def device_id(self, val):
        """Device-ID setter.

        Args:
            val (int): Device_ID
        """
        self.__device_id = val

    @property
    def is_equip(self):
        pass

    @is_equip.setter
    def is_equip(self, val):
        """is-Equipment setter.

        Args:
            val (bool): is-Equipment
        """
        self.__is_equip = bool(val)

    @is_equip.getter
    def is_equip(self):
        """is-Equipment getter.

        Returns:
            bool: True if Equipment
        """
        return self.__is_equip

    @property
    def name(self):
        pass

    @name.setter
    def name(self, val):
        """Communicator-Name setter.

        Args:
            val (str or None): Communicator-Name
        """
        self.__name = val if val is None else str(val)

    @name.getter
    def name(self):
        """Communicator-Name getter.

        Returns:
            str: Communicator-Name
        """
        return self.__name

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

    @property
    def timeout_t1(self):
        pass

    @timeout_t1.getter
    def timeout_t1(self):
        """Timeout-T1 getter.

        Returns:
            float: Timeout-T1
        """
        return self.__timeout_t1

    @timeout_t1.setter
    def timeout_t1(self, val):
        """Timeout-T1 setter.

        Args:
            v (int or float): Timeout-T1 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t1 = self._tstx(val)

    @property
    def timeout_t2(self):
        pass

    @timeout_t2.getter
    def timeout_t2(self):
        """Timeout-T2 getter.

        Returns:
            float: Timeout-T2
        """
        return self.__timeout_t2

    @timeout_t2.setter
    def timeout_t2(self, val):
        """Timeout-T2 setter.

        Args:
            v (int or float): Timeout-T2 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t2 = self._tstx(val)

    @property
    def timeout_t3(self):
        pass

    @timeout_t3.getter
    def timeout_t3(self):
        """Timeout-T3 getter.

        Returns:
            float: Timeout-T3
        """
        return self.__timeout_t3

    @timeout_t3.setter
    def timeout_t3(self, val):
        """Timeout-T3 setter.

        Args:
            v (int or float): Timeout-T3 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t3 = self._tstx(val)

    @property
    def timeout_t4(self):
        pass

    @timeout_t4.getter
    def timeout_t4(self):
        """Timeout-T4 getter.

        Returns:
            float: Timeout-T4
        """
        return self.__timeout_t4

    @timeout_t4.setter
    def timeout_t4(self, val):
        """Timeout-T4 setter.

        Args:
            v (int or float): Timeout-T4 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t4 = self._tstx(val)

    @property
    def timeout_t5(self):
        pass

    @timeout_t5.getter
    def timeout_t5(self):
        """Timeout-T5 getter.

        Returns:
            float: Timeout-T5
        """
        return self.__timeout_t5

    @timeout_t5.setter
    def timeout_t5(self, val):
        """Timeout-T5 setter.

        Args:
            v (int or float): Timeout-T5 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t5 = self._tstx(val)

    @property
    def timeout_t6(self):
        pass

    @timeout_t6.getter
    def timeout_t6(self):
        """Timeout-T6 getter.

        Returns:
            float: Timeout-T6
        """
        return self.__timeout_t6

    @timeout_t6.setter
    def timeout_t6(self, val):
        """Timeout-T6 setter.

        Args:
            v (int or float): Timeout-T6 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t6 = self._tstx(val)

    @property
    def timeout_t7(self):
        pass

    @timeout_t7.getter
    def timeout_t7(self):
        """Timeout-T7 getter.

        Returns:
            float: Timeout-T7
        """
        return self.__timeout_t7

    @timeout_t7.setter
    def timeout_t7(self, val):
        """Timeout-T7 setter.

        Args:
            v (int or float): Timeout-T7 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t7 = self._tstx(val)

    @property
    def timeout_t8(self):
        pass

    @timeout_t8.getter
    def timeout_t8(self):
        """Timeout-T8 getter.

        Returns:
            float: Timeout-T8
        """
        return self.__timeout_t8

    @timeout_t8.setter
    def timeout_t8(self, val):
        """Timeout-T8 setter.

        Args:
            v (int or float): Timeout-T8 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t8 = self._tstx(val)

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

        if not self.is_open:
            self._open()

        while True:
            if self.is_closed:
                raise SecsCommunicatorError("Communicator closed")
            if self.is_communicating:
                return
            with self.__comm_condition:
                self.__comm_condition.wait()

    @property
    def is_open(self):
        pass

    @is_open.getter
    def is_open(self):
        with self.__open_close_rlock:
            return self.__opened and not self.__closed

    @property
    def is_closed(self):
        pass

    @is_closed.getter
    def is_closed(self):
        with self.__open_close_rlock:
            return self.__closed
    
    def _set_opened(self):
        with self.__open_close_rlock:
            self.__opened = True

    def _set_closed(self):
        with self.__open_close_rlock:
            self.__closed = True
            with self.__comm_condition:
                self.__comm_condition.notify_all()

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
            self.device_id)

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
            self.device_id)

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
        d = self.device_id if self.is_equip else 0
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

    def add_recv_primary_msg_listener(self, l):
        self.__recv_primary_msg_lstnrs.append(l)

    def remove_recv_priary_msg_listener(self, l):
        self.__recv_primary_msg_lstnrs.remove(l)

    def _put_recv_primary_msg(self, recv_msg):
        if recv_msg is not None:
            for lstnr in self.__recv_primary_msg_lstnrs:
                lstnr(recv_msg, self)

    def add_recv_all_msg_listener(self, l):
        self.__recv_all_msg_lstnrs.append(l)

    def remove_recv_all_msg_listener(self, l):
        self.__recv_all_msg_lstnrs.remove(l)
    
    def _put_recv_all_msg(self, recv_msg):
        if recv_msg is not None:
            for lstnr in self.__recv_all_msg_lstnrs:
                lstnr(recv_msg, self)
    
    def add_sended_msg_listener(self, l):
        self.__sended_msg_lstnrs.append(l)

    def remove_sended_msg_listener(self, l):
        self.__sended_msg_lstnrs.remove(l)

    def _put_sended_msg(self, sended_msg):
        if sended_msg is not None:
            for lstnr in self.__sended_msg_lstnrs:
                lstnr(sended_msg, self)
    
    def add_communicate_listener(self, l):
        with self.__comm_rlock:
            self.__communicate_lstnrs.append(l)
            l(self.__communicating, self)

    def remove_communicate_listener(self, l):
        with self.__comm_rlock:
            self.__communicate_lstnrs.remove(l)

    def _put_communicated(self, communicating):
        with self.__comm_rlock:
            if communicating != self.__communicating:
                self.__communicating = communicating
                for lstnr in self.__communicate_lstnrs:
                    lstnr(self.__communicating, self)
                with self.__comm_condition:
                    self.__comm_condition.notify_all()

    @property
    def is_communicating(self):
        pass

    @is_communicating.getter
    def is_communicating(self):
        with self.__comm_rlock:
            return self.__communicating

    def add_error_listener(self, l):
        self.__error_listeners.append(l)

    def remove_error_listener(self, l):
        self.__error_listeners.remove(l)

    def _put_error(self, e):
        for lstnr in self.__error_listeners:
            lstnr(e, self)
