import secs


class HsmsSsMessageParseError(secs.SecsMessageParseError):

    def __init__(self, msg):
        super(HsmsSsMessageParseError, self).__init__(msg)


class HsmsSsControlType:

    UNDEFINED = (0xFF, 0xFF)

    DATA = (0x00, 0x00)
    SELECT_REQ = (0x00, 0x01)
    SELECT_RSP = (0x00, 0x02)
    DESELECT_REQ = (0x00, 0x03)
    DESELECT_RSP = (0x00, 0x04)
    LINKTEST_REQ = (0x00, 0x05)
    LINKTEST_RSP = (0x00, 0x06)
    REJECT_REQ = (0x00, 0x07)
    SEPARATE_REQ = (0x00, 0x09)

    __ITEMS = (
        DATA,
        SELECT_REQ, SELECT_RSP,
        DESELECT_REQ, DESELECT_RSP,
        LINKTEST_REQ, LINKTEST_RSP,
        REJECT_REQ,
        SEPARATE_REQ
    )

    @classmethod
    def get(cls, v):
        for x in cls.__ITEMS:
            if x[0] == v[0] and x[1] == v[1]:
                return x
        return cls.UNDEFINED

    @classmethod
    def has_s_type(cls, b):
        for x in cls.__ITEMS:
            if x[1] == b:
                return True
        return False


class HsmsSsSelectStatus():

    UNKNOWN = 0xFF

    SUCCESS = 0x00
    ACTIVED = 0x01
    NOT_READY = 0x02
    ALREADY_USED = 0x03

    __ITEMS = (
        SUCCESS,
        ACTIVED,
        NOT_READY,
        ALREADY_USED
    )

    @classmethod
    def get(cls, b):
        for x in cls.__ITEMS:
            if x == b:
                return x
        return cls.UNKNOWN


class HsmsSsRejectReason():

    UNKNOWN = 0xFF

    NOT_SUPPORT_TYPE_S = 0x01
    NOT_SUPPORT_TYPE_P = 0x02
    TRANSACTION_NOT_OPEN = 0x03
    NOT_SELECTED = 0x04

    __ITEMS = (
        NOT_SUPPORT_TYPE_S,
        NOT_SUPPORT_TYPE_P,
        TRANSACTION_NOT_OPEN,
        NOT_SELECTED
    )

    @classmethod
    def get(cls, b):
        for x in cls.__ITEMS:
            if x == b:
                return x
        return cls.UNKNOWN


class HsmsSsMessage(secs.SecsMessage):

    def __init__(self, strm, func, wbit, secs2body, system_bytes, control_type):
        super(HsmsSsMessage, self).__init__(strm, func, wbit, secs2body)
        self._system_bytes = system_bytes
        self._control_type = control_type
        self._cache_msg_length = None
        self._cache_str = None
        self._cache_repr = None
        self._cache_bytes = None

    def __str__(self):
        if self._cache_str is None:
            vv = [self._header10bytes_str(), ' length:', str(self._msg_length())]
            if self._control_type == HsmsSsControlType.DATA:
                vv.extend([
                    self._STR_LINESEPARATOR,
                    'S', str(self.strm),
                    'F', str(self.func)
                ])
                if self.wbit:
                    vv.append(' W')
                if self.secs2body is not None:
                    vv.extend([
                        self._STR_LINESEPARATOR,
                        self.secs2body.to_sml()
                    ])
                vv.append('.')
            self._cache_str = ''.join(vv)
        return self._cache_str

    def __repr__(self):
        if self._cache_repr is None:
            vv = ["{'header':", str(self._header10bytes())]
            if self._control_type == HsmsSsControlType.DATA:
                vv.extend([
                    ",'strm':", str(self.strm),
                    ",'func':", str(self.func),
                    ",'wbit':", str(self.wbit)
                ])
                if self.secs2body is not None:
                    vv.extend([",'secs2body':", repr(self.secs2body)])
            vv.append("}")
            self._cache_repr = ''.join(vv)
        return self._cache_repr

    def _msg_length(self):
        if self._cache_msg_length is None:
            i = len(self._header10bytes())
            if self.secs2body is not None:
                i += len(self.secs2body.to_bytes())
            self._cache_msg_length = i

        return self._cache_msg_length

    def get_control_type(self):
        return self._control_type

    def get_p_type(self):
        return self._control_type[0]

    def get_s_type(self):
        return self._control_type[1]

    def get_select_status(self):
        return HsmsSsSelectStatus.get((self._header10bytes())[3])

    def get_reject_reason(self):
        return HsmsSsRejectReason.get((self._header10bytes())[3])

    def to_bytes(self):
        if self._cache_bytes is None:
            msglen = self._msg_length()
            vv = [
                bytes([
                    (msglen >> 24) & 0xFF,
                    (msglen >> 16) & 0xFF,
                    (msglen >> 8) & 0xFF,
                    msglen & 0xFF
                ]),
                self._header10bytes(),
                b'' if self.secs2body is None else self.secs2body.to_bytes()
            ]
            self._cache_bytes = b''.join(vv)
        return self._cache_bytes
        
    @classmethod
    def from_bytes(cls, bs):

        h10bs = bs[4:14]
        sysbs = h10bs[6:10]

        ctrl_type = HsmsSsControlType.get(h10bs[4:6])

        if ctrl_type == HsmsSsControlType.DATA:

            devid = (h10bs[0] << 8) | h10bs[1]
            strm = h10bs[2] & 0x7F
            func = h10bs[3]
            wbit = (h10bs[2] & 0x80) == 0x80

            if len(bs) > 14:
                s2b = secs.Secs2BodyBuilder.from_body_bytes(bs[14:])
                v = HsmsSsDataMessage(strm, func, wbit, s2b, sysbs, devid)
            else:
                v = HsmsSsDataMessage(strm, func, wbit, None, sysbs, devid)
            
        else:

            v = HsmsSsControlMessage(sysbs, ctrl_type)
            v._p_type = h10bs[2]
            v._s_type = h10bs[3]

        v._cache_bytes = bs
        v._cache_header10bytes = h10bs
        
        return v


class HsmsSsDataMessage(HsmsSsMessage):

    def __init__(self, strm, func, wbit, secs2body, system_bytes, session_id):
        super(HsmsSsDataMessage, self).__init__(strm, func, wbit, secs2body, system_bytes, HsmsSsControlType.DATA)
        self.__session_id = session_id
        self._cache_header10bytes = None

    def _header10bytes(self):
        if self._cache_header10bytes is None:
            b2 = self.strm
            if self.wbit:
                b2 |= 0x80
            self._cache_header10bytes = bytes([
                (self.session_id >> 8) & 0x7F,
                self.session_id & 0xFF,
                b2, self.func,
                self._control_type[0], self._control_type[1],
                self._system_bytes[0], self._system_bytes[1],
                self._system_bytes[2], self._system_bytes[3]
                ])
        
        return self._cache_header10bytes

    @property
    def session_id(self):
        pass

    @session_id.getter
    def session_id(self):
        return self.__session_id

    def _device_id(self):
        return self.session_id


class HsmsSsControlMessage(HsmsSsMessage):

    def __init__(self, system_bytes, control_type):
        super(HsmsSsControlMessage, self).__init__(0, 0, False, None, system_bytes, control_type)
        self._cache_header10bytes = None

    CONTROL_DEVICE_ID = -1

    def _device_id(self):
        return self.CONTROL_DEVICE_ID

    def _header10bytes(self):
        if self._cache_header10bytes is None:
            self._cache_header10bytes = bytes([
                0xFF, 0xFF,
                0x00, 0x00,
                self._control_type[0], self._control_type[1],
                self._system_bytes[0], self._system_bytes[1],
                self._system_bytes[2], self._system_bytes[3]
                ])
        
        return self._cache_header10bytes

    @classmethod
    def build_select_request(cls, system_bytes):
        return HsmsSsControlMessage(system_bytes, HsmsSsControlType.SELECT_REQ)
    
    @classmethod
    def build_select_response(cls, primary_msg, select_status):
        ctrl_type = HsmsSsControlType.SELECT_RSP
        sys_bytes = (primary_msg._header10bytes())[6:10]
        r = HsmsSsControlMessage(sys_bytes, ctrl_type)
        r._cache_header10bytes = bytes([
            0xFF, 0xFF,
            0x00, select_status,
            ctrl_type[0], ctrl_type[1],
            sys_bytes[0], sys_bytes[1],
            sys_bytes[2], sys_bytes[3]
            ])
        return r

    @classmethod
    def build_linktest_request(cls, system_bytes):
        return HsmsSsControlMessage(system_bytes, HsmsSsControlType.LINKTEST_REQ)

    @classmethod
    def build_linktest_response(cls, primary_msg):
        return HsmsSsControlMessage(
            (primary_msg._header10bytes())[6:10],
            HsmsSsControlType.LINKTEST_RSP)

    @classmethod
    def build_reject_request(cls, primary_msg, reject_reason):
        ctrl_type = HsmsSsControlType.REJECT_REQ
        h10bytes = primary_msg._header10bytes()
        b2 = h10bytes[4] if reject_reason == HsmsSsRejectReason.NOT_SUPPORT_TYPE_P else h10bytes[5]
        sys_bytes = h10bytes[6:10]
        r = HsmsSsControlMessage(sys_bytes, ctrl_type)
        r._cache_header10bytes = bytes([
            0xFF, 0xFF,
            b2, reject_reason,
            ctrl_type[0], ctrl_type[1],
            sys_bytes[0], sys_bytes[1],
            sys_bytes[2], sys_bytes[3]
            ])
        return r
    
    @classmethod
    def build_separate_request(cls, system_bytes):
        return HsmsSsControlMessage(system_bytes, HsmsSsControlType.SEPARATE_REQ)
