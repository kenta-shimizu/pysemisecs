import struct
import threading
import os
import concurrent.futures
import socket
import re


class Secs2BodyParseError(Exception):

    def __init__(self, msg):
        super(Secs2BodyParseError, self).__init__(msg)


class Secs2BodyBytesParseError(Secs2BodyParseError):

    def __init__(self, msg):
        super(Secs2BodyBytesParseError, self).__init__(msg)


class AbstractSecs2Body:

    _BYTES_LEN_3 = 2**16
    _BYTES_LEN_2 = 2**8
    _SML_TAB = '  '
    _SML_VALUESEPARATOR = ' '
    _SML_LINESEPARATOR = os.linesep

    def __init__(self, item_type, value):
        self._type = item_type
        self._value = value
        self._cache_sml = None
        self._cache_repr = None
        self._cache_bytes = None

    def __str__(self):
        return self.to_sml()

    def __repr__(self):
        if self._cache_repr is None:
            self._cache_repr = str((self._type[0], self._value))
        return self._cache_repr

    def __len__(self):
        return len(self._value)

    def __getitem__(self, item):
        return self._value[item]

    def __iter__(self):
        return iter(self._value)

    def __next__(self):
        return next(self._value)

    @property
    def type(self):
        pass

    @type.getter
    def type(self):
        """[summary]

        Alias of get_type()

        Returns:
            str: 'L', 'A', 'BOOLEAN', 'B', 'I1', 'I2', 'I4', 'I8', 'U1', 'U2', 'U4', 'U8', 'F4', 'F8'
        """
        return self._type[0]

    def get_type(self, *indices):
        """ITEM type getter.

        Returns:
            str: 'L', 'A', 'BOOLEAN', 'B', 'I1', 'I2', 'I4', 'I8', 'U1', 'U2', 'U4', 'U8', 'F4', 'F8'
        """
        v = self
        for i in indices:
            v = v[i]

        return v._type[0]

    @property
    def value(self):
        pass

    @value.getter
    def value(self):
        """value getter.

        Returns:
            Any: value
        """
        return self._value

    def get_value(self, *indices):
        """value getter.

        Returns:
            Any: seek value.
        """
        v = self
        for i in indices:
            v = v[i]

        if isinstance(v, AbstractSecs2Body):
            return v._value
        else:
            return v

    def to_sml(self):
        """SML getter.

        Returns:
            str: SML
        """
        if self._cache_sml is None:
            self._cache_sml = self._create_to_sml()
        return self._cache_sml

    def to_bytes(self):
        """bytes getter.

        Returns:
            bytes: bytes
        """
        if self._cache_bytes is None:
            self._cache_bytes = self._create_to_bytes()
        return self._cache_bytes

    def _create_to_sml(self):
        l, v = self._create_to_sml_value()
        return '<' + self._type[0] + ' [' + str(l) + '] ' + str(v) + ' >'

    def _create_to_sml_value(self):
        return (0, '')

    def _create_to_bytes(self):
            bsvv = self._create_to_bytes_value()
            vlen = len(bsvv)
            bslen = struct.pack('>L', vlen)
            if vlen >= self._BYTES_LEN_3:
                return struct.pack('>B', (self._type[1] | 0x03)) + bslen[1:4] + bsvv
            elif vlen >= self._BYTES_LEN_2:
                return struct.pack('>B', (self._type[1] | 0x02)) + bslen[2:4] + bsvv
            else:
                return struct.pack('>B', (self._type[1] | 0x01)) + bslen[3:4] + bsvv

    def _create_to_bytes_value(self):
        return self._value

    @staticmethod
    def _tiof(value, item_size, is_signed):    # test_int_overflow return int_value

        if type(value) is str and value.upper().startswith("0X"):
            v = int(value[2:], 16)
        else:
            v = int(value)

        n = item_size * 8

        if is_signed:
            n -= 1

        x = 2**n
        max = x-1

        if is_signed:
            min = -x
        else:
            min = 0

        if v > max or v < min:
            raise ValueError("value is from " + str(min) + " to " + str(max) + ", value is " + str(v))

        return v


class Secs2AsciiBody(AbstractSecs2Body):

    def __init__(self, item_type, value):
        super(Secs2AsciiBody, self).__init__(item_type, str(value))

    def _create_to_sml_value(self):
        return (len(self._value), '"' + self._value + '"')

    def _create_to_bytes_value(self):
        return self._value.encode(encoding='ascii')

    @staticmethod
    def build(item_type, value):
        return Secs2AsciiBody(item_type, value)


class Secs2BooleanBody(AbstractSecs2Body):

    def __init__(self, item_type, value):
        tv = type(value)
        if tv is tuple or tv is list:
            super(Secs2BooleanBody, self).__init__(
                item_type,
                tuple([bool(x) for x in value])
                )
        else:
            super(Secs2BooleanBody, self).__init__(
                item_type,
                tuple([bool(value)])
                )

    def _create_to_sml_value(self):
        vv = [("TRUE" if x else "FALSE") for x in self._value]
        return (len(vv), self._SML_VALUESEPARATOR.join(vv))

    def _create_to_bytes_value(self):
        return bytes([(0xFF if v else 0x00) for v in self._value])

    @staticmethod
    def build(item_type, value):
        return Secs2BooleanBody(item_type, value)


class Secs2BinaryBody(AbstractSecs2Body):

    def __init__(self, item_type, value):
        tv = type(value)
        if tv is bytes:
            super(Secs2BinaryBody, self).__init__(item_type, value)
        elif tv is bytearray:
            super(Secs2BinaryBody, self).__init__(item_type, bytes(value))
        elif tv is tuple or tv is list:
            super(Secs2BinaryBody, self).__init__(
                item_type,
                bytes([self._tiof(x, item_type[2], item_type[4]) for x in value])
                )
        else:
            super(Secs2BinaryBody, self).__init__(
                item_type,
                bytes([self._tiof(value, item_type[2], item_type[4])])
                )

    def _create_to_sml_value(self):
        vv = [('0x' + '{:02X}'.format(x)) for x in self._value]
        return (len(vv), self._SML_VALUESEPARATOR.join(vv))

    @staticmethod
    def build(item_type, value):
        return Secs2BinaryBody(item_type, value)


class AbstractSecs2NumberBody(AbstractSecs2Body):

    def __init__(self, item_type, value):
        super(AbstractSecs2NumberBody, self).__init__(item_type, tuple(value))

    def _create_to_sml_value(self):
        vv = [str(x) for x in self._value]
        return (len(vv), self._SML_VALUESEPARATOR.join(vv))

    def _create_to_bytes_value(self):
        return b''.join([struct.pack(('>' + self._type[3]), x) for x in self._value])


class Secs2IntegerBody(AbstractSecs2NumberBody):

    def __init__(self, item_type, value):
        tv = type(value)
        if tv is tuple or tv is list:
            super(Secs2IntegerBody, self).__init__(
                item_type,
                [self._tiof(x, item_type[2], item_type[4]) for x in value]
                )
        else:
            super(Secs2IntegerBody, self).__init__(
                item_type,
                [self._tiof(value, item_type[2], item_type[4])]
                )

    @staticmethod
    def build(item_type, value):
        return Secs2IntegerBody(item_type, value)


class Secs2FloatBody(AbstractSecs2NumberBody):

    def __init__(self, item_type, value):
        tv = type(value)
        if tv is tuple or tv is list:
            super(Secs2FloatBody, self).__init__(item_type, [float(x) for x in value])
        else:
            super(Secs2FloatBody, self).__init__(item_type, [float(value)])

    @staticmethod
    def build(item_type, value):
        return Secs2FloatBody(item_type, value)


class Secs2ListBody(AbstractSecs2Body):

    def __init__(self, item_type, value):

        tv = type(value)
        if tv is tuple or tv is list:

            vv = list()
            for x in value:
                if isinstance(x, AbstractSecs2Body):
                    vv.append(x)
                else:
                    tx = type(x)
                    if (tx is tuple or tx is list) and (len(x) == 2):
                        vv.append(Secs2BodyBuilder.build(x[0], x[1]))
                    else:
                        raise TypeError("L value require tuple or list, and length == 2")

            super(Secs2ListBody, self).__init__(item_type, tuple(vv))

        else:
            raise TypeError("L values require tuple or list")

    def _create_to_sml(self):

        def _lsf(value, level=''):  # create_list_sml_string
            deep_level = level + self._SML_TAB
            vv = list()
            vv.append(level + '<L [' + str(len(value)) + ']')
            for x in value:
                if x._type[0] == 'L':
                    vv.append(_lsf(x._value, deep_level))
                else:
                    vv.append(deep_level + x.to_sml())
            vv.append(level + '>')
            return self._SML_LINESEPARATOR.join(vv)

        return _lsf(self._value)

    def _create_to_bytes(self):
        vlen = len(self._value)
        bslen = struct.pack('>L', vlen)
        bsvv = b''.join([x.to_bytes() for x in self._value])
        if vlen >= self._BYTES_LEN_3:
            return struct.pack('>B', (self._type[1] | 0x03)) + bslen[1:4] + bsvv
        elif vlen >= self._BYTES_LEN_2:
            return struct.pack('>B', (self._type[1] | 0x02)) + bslen[2:4] + bsvv
        else:
            return struct.pack('>B', (self._type[1] | 0x01)) + bslen[3:4] + bsvv

    @staticmethod
    def build(item_type, value):
        return Secs2ListBody(item_type, value)


class Secs2BodyBuilder:

    _ITEMS = (
        ('L',       0x00, -1, None, None,   Secs2ListBody.build),
        ('B',       0x20,  1, 'c',  False,  Secs2BinaryBody.build),
        ('BOOLEAN', 0x24,  1, '?',  None,   Secs2BooleanBody.build),
        ('A',       0x40, -1, None, None,   Secs2AsciiBody.build),
        ('I8',      0x60,  8, 'q',  True,   Secs2IntegerBody.build),
        ('I1',      0x64,  1, 'b',  True,   Secs2IntegerBody.build),
        ('I2',      0x68,  2, 'h',  True,   Secs2IntegerBody.build),
        ('I4',      0x70,  4, 'l',  True,   Secs2IntegerBody.build),
        ('F8',      0x80,  8, 'd',  None,   Secs2FloatBody.build),
        ('F4',      0x90,  4, 'f',  None,   Secs2FloatBody.build),
        ('U8',      0xA0,  8, 'Q',  False,  Secs2IntegerBody.build),
        ('U1',      0xA4,  1, 'B',  False,  Secs2IntegerBody.build),
        ('U2',      0xA8,  2, 'H',  False,  Secs2IntegerBody.build),
        ('U4',      0xB0,  4, 'L',  False,  Secs2IntegerBody.build)
    )

    @classmethod
    def build(cls, item_type, value):

        if item_type is None:
            raise TypeError("Not accept None")

        tt = type(item_type)

        if tt is str:
            ref_type = cls.get_item_type_from_sml(item_type)
        elif tt is tuple:
            ref_type = item_type
        else:
            raise TypeError("Require str or tuple")

        return ref_type[5](ref_type, value)

    @classmethod
    def get_item_type_from_sml(cls, sml_item_type):
        str_upper = sml_item_type.upper()
        for i in cls._ITEMS:
            if i[0] == str_upper:
                return i
        raise ValueError("'" + sml_item_type + "' not found")

    @classmethod
    def from_body_bytes(cls, body_bytes):

        def _itr(b):    # get_item_type
            x = b & 0xFC
            for i in cls._ITEMS:
                if i[1] == x:
                    return i
            raise ValueError('0x' + '{:02X}'.format(b) + " not found")

        def _xr(bs, pos):   # get (item_type, value_length, shift_position)

            b = bs[pos]
            t = _itr(b)
            len_bit = b & 0x3

            if len_bit == 3:
                lenbs = (bs[pos+1] << 16) | (bs[pos+2] << 8) | bs[pos+3]
            elif len_bit == 2:
                lenbs = (bs[pos+1] << 8) | bs[pos+2]
            else:
                lenbs = bs[pos+1]

            return (t, lenbs, (len_bit + 1))

        def _f(bs, pos):

            r = _xr(bs, pos)
            tt, v_len, b_len = _xr(bs, pos)
            start_index = pos + b_len
            end_index = pos + b_len + v_len

            if tt[0] == 'L':
                vv = list()
                p = start_index
                for _ in range(r[1]):
                    v, p = _f(bs, p)
                    vv.append(v)
                return (tt[5](tt, vv), p)

            elif tt[0] == 'BOOLEAN':
                vv = [(b != 0x00) for b in bs[start_index:end_index]]
                return (tt[5](tt, vv), end_index)

            elif tt[0] == 'A':
                v = bs[start_index:end_index].decode(encoding='ascii')
                return (tt[5](tt, v), end_index)

            elif tt[0] == 'B':
                vv = bs[start_index:end_index]
                return (tt[5](tt, vv), end_index)

            elif tt[0] in ('I1', 'I2', 'I4', 'I8', 'F8', 'F4', 'U1', 'U2', 'U4', 'U8'):
                vv = list()
                p = start_index
                for _ in range(0, v_len, tt[2]):
                    prev = p
                    p += tt[2]
                    v = struct.unpack(('>' + tt[3]), bs[prev:p])
                    vv.append(v[0])
                return (tt[5](tt, vv), end_index)

        try:
            if len(body_bytes) == 0:
                return None

            r, p = _f(body_bytes, 0)
            length = len(body_bytes)

            if p == length:
                r._cache_bytes = bytes(body_bytes)
                return r
            else:
                raise Secs2BodyBytesParseError("not reach bytes end, reach=" + str(p) + ", length=" + str(length))

        except ValueError as e:
            raise Secs2BodyBytesParseError(e)
        except TypeError as e:
            raise Secs2BodyBytesParseError(e)
        except IndexError as e:
            raise Secs2BodyBytesParseError(e)


class SmlParseError(Exception):

    def __init__(self, msg):
        super(SmlParseError, self).__init__(msg)


class Secs2BodySmlParseError(SmlParseError):

    def __init__(self, msg):
        super(Secs2BodySmlParseError, self).__init__(msg)


class SmlParser:

    _SML_PATTERN = '[Ss]([0-9]{1,3})[Ff]([0-9]{1,3})\\s*([Ww]?)\\s*((<.*>)?)\\s*\\.$'
    _SML_PROG = re.compile(_SML_PATTERN)

    @classmethod
    def parse(cls, sml_str):
        """parse from SML to Tuple

        Args:
            sml_str (str): SML string.

        Raises:
            Secs2BodySmlParseError: raise if Secs2body parse failed.
            SmlParseError: raise if SML parse failed.

        Returns:
            tuple: (
                Stream-Number (int),
                Function-Number (int),
                has-WBit (bool),
                Secs2Body or None
                )
        """

        s = sml_str.replace('\n', ' ').strip()
        if not s.endswith("."):
            raise SmlParseError("SML not endswith '.'")

        x = cls._SML_PROG.match(s)
        if x is None:
            raise SmlParseError("SML not match")

        body = x.group(4)

        return (
            int(x.group(1)),
            int(x.group(2)),
            len(x.group(3)) > 0,
            cls._parse_body(body) if len(body) > 0 else None
        )

    @classmethod
    def _parse_body(cls, sml_str):

        def _is_ws(v):  # is_white_space
            return (v.encode(encoding='ascii'))[0] <= 0x20

        def _seek_next(s, from_pos, *args):
            p = from_pos
            if len(args) > 0:
                while True:
                    v = s[p]
                    for a in args:
                        if type(a) is str:
                            if v == a:
                                return (v, p)
                        else:
                            if a(v):
                                return (v, p)
                    p += 1
            else:
                while True:
                    v = s[p]
                    if _is_ws(v):
                        p += 1
                    else:
                        return (v, p)

        def _ssbkt(s, from_pos):    # seek size_start_blacket'[' position, return position, -1 if not exist
            v, p = _seek_next(s, from_pos)
            return p if v == '[' else -1

        def _sebkt(s, from_pos):    # seek size_end_blacket']' position, return position
            return (_seek_next(s, from_pos, ']'))[1]

        def _isbkt(s, from_pos):    # seek item_start_blacket'<' position, return position, -1 if not exist
            v, p = _seek_next(s, from_pos)
            return p if v == '<' else -1

        def _iebkt(s, from_pos):    # seek item_end_blacket'>' position, return position
            return (_seek_next(s, from_pos, '>'))[1]

        def _seek_item(s, from_pos):  # seek item_type, return (item_type, shifted_position)
            p_start = (_seek_next(s, from_pos))[1]
            p_end = (_seek_next(s, (p_start + 1), '[', '"', '<', '>', _is_ws))[1]
            return (Secs2BodyBuilder.get_item_type_from_sml(s[p_start:p_end]), p_end)

        def _f(s, from_pos):

            p = _isbkt(s, from_pos)

            if p < 0:
                raise Secs2BodySmlParseError("Not start < bracket")

            tt, p = _seek_item(s, (p + 1))

            r = _ssbkt(s, p)
            if r >= 0:
                p = _sebkt(s, (r + 1)) + 1

            if tt[0] == 'L':
                vv = list()
                while True:
                    v, p = _seek_next(s, p)
                    if v == '>':
                        return (tt[5](tt, vv), (p + 1))

                    elif v == '<':
                        r, p = _f(s, p)
                        vv.append(r)

                    else:
                        raise Secs2BodySmlParseError("Not reach LIST end")

            elif tt[0] == 'BOOLEAN':
                r = _iebkt(s, p)
                vv = list()
                for x in s[p:r].strip().split():
                    ux = x.upper()
                    if ux == 'TRUE' or ux == 'T':
                        vv.append(True)
                    elif ux == 'FALSE' or ux == 'F':
                        vv.append(False)
                    else:
                        raise Secs2BodySmlParseError("Not accept, BOOELAN require TRUE or FALSE")
                return (tt[5](tt, vv), (r + 1))

            elif tt[0] == 'A':
                vv = list()
                while True:
                    v, p_start = _seek_next(s, p)
                    if v == '>':
                        return (tt[5](tt, ''.join(vv)), (p_start + 1))

                    elif v == '"':
                        v, p_end = _seek_next(s, (p_start + 1), '"')
                        vv.append(s[(p_start+1):p_end])
                        p = p_end + 1

                    elif v == '0':
                        if s[p_start + 1] not in ('X', 'x'):
                            raise Secs2BodySmlParseError("Ascii not accept 0xNN")
                        v, p = _seek_next(s, (p_start+2), '"', '>', _is_ws)
                        vv.append(bytes([int(s[(p_start+2):p], 16)]).decode(encoding='ascii'))

                    else:
                        raise Secs2BodySmlParseError("Ascii not reach end")

            elif tt[0] in ('B', 'I1', 'I2', 'I4', 'I8', 'F4', 'F8', 'U1', 'U2', 'U4', 'U8'):
                r = _iebkt(s, p)
                return (tt[5](tt, s[p:r].strip().split()), (r + 1))

        try:
            if sml_str is None:
                raise Secs2BodySmlParseError("Not accept None")

            ss = str(sml_str).strip()
            r, p = _f(ss, 0)
            if len(ss[p:]) > 0:
                raise Secs2BodySmlParseError("Not reach end, end=" + str(p) + ", length=" + str(len(ss)))
            return r

        except TypeError as e:
            raise Secs2BodySmlParseError(str(e))
        except ValueError as e:
            raise Secs2BodySmlParseError(str(e))
        except IndexError as e:
            raise Secs2BodySmlParseError(str(e))


class SecsMessageParseError(Exception):

    def __init__(self, msg):
        super(SecsMessageParseError, self).__init__(msg)


class SecsMessage:

    _STR_LINESEPARATOR = os.linesep

    def __init__(self, strm, func, wbit, secs2body):

        if strm < 0 or strm > 127:
            raise SecsMessageParseError("Stream is from 0 to 127")

        if func < 0 or func > 255:
            raise SecsMessageParseError("Function is from 0 to 255")

        self.__strm = int(strm)
        self.__func = int(func)
        self.__wbit = bool(wbit)
        self.__secs2body = secs2body
        self.__cache_header10bytes_str = None

    @property
    def strm(self):
        pass

    @strm.getter
    def strm(self):
        return self.__strm

    def get_stream(self):
        """Stream-Number getter.

        Alias of self.strm

        Returns:
            int: Stream-Number
        """
        return self.strm

    @property
    def func(self):
        pass

    @func.getter
    def func(self):
        return self.__func

    def get_function(self):
        """Function-Number getter.

        Alias of self.func

        Returns:
            int: Function-Number
        """
        return self.func

    @property
    def wbit(self):
        pass

    @wbit.getter
    def wbit(self):
        return self.__wbit

    def has_wbit(self):
        """W-Bit getter

        Alias of self.wbit

        Returns:
            bool: True if has W-Bit
        """
        return self.wbit

    @property
    def secs2body(self):
        pass

    @secs2body.getter
    def secs2body(self):
        return self.__secs2body

    def get_secs2body(self):
        """Secs2Body getter.

        Alias of self.secs2body

        Returns:
            <Secs2Body>: Secs2Body
        """
        return self.secs2body

    @property
    def device_id(self):
        pass

    @device_id.getter
    def device_id(self):
        """Device-ID getter.

        Returns:
            int: Device-ID
        """
        return self._device_id()

    def _device_id(self):
        # prototype
        return -1

    def get_system_bytes(self):
        return (self._header10bytes())[6:10]

    def _header10bytes(self):
        return bytes(10)

    def _header10bytes_str(self):

        if self.__cache_header10bytes_str is None:

            x = self._header10bytes()
            self.__cache_header10bytes_str = (
                '[' + '{:02X}'.format(x[0])
                + ' ' + '{:02X}'.format(x[1])
                + '|' + '{:02X}'.format(x[2])
                + ' ' + '{:02X}'.format(x[3])
                + '|' + '{:02X}'.format(x[4])
                + ' ' + '{:02X}'.format(x[5])
                + '|' + '{:02X}'.format(x[6])
                + ' ' + '{:02X}'.format(x[7])
                + ' ' + '{:02X}'.format(x[8])
                + ' ' + '{:02X}'.format(x[9])
                + ']')

        return self.__cache_header10bytes_str


class HsmsSsMessageParseError(SecsMessageParseError):

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

    _ITEMS = (
        DATA,
        SELECT_REQ, SELECT_RSP,
        DESELECT_REQ, DESELECT_RSP,
        LINKTEST_REQ, LINKTEST_RSP,
        REJECT_REQ,
        SEPARATE_REQ
    )

    @classmethod
    def get(cls, v):
        for x in cls._ITEMS:
            if x[0] == v[0] and x[1] == v[1]:
                return x
        return cls.UNDEFINED

    @classmethod
    def has_s_type(cls, b):
        for x in cls._ITEMS:
            if x[1] == b:
                return True
        return False


class HsmsSsSelectStatus():

    UNKNOWN = 0xFF

    SUCCESS = 0x00
    ACTIVED = 0x01
    NOT_READY = 0x02
    ALREADY_USED = 0x03

    _ITEMS = (
        SUCCESS,
        ACTIVED,
        NOT_READY,
        ALREADY_USED
    )

    @classmethod
    def get(cls, b):
        for x in cls._ITEMS:
            if x == b:
                return x
        return cls.UNKNOWN


class HsmsSsRejectReason():

    UNKNOWN = 0xFF

    NOT_SUPPORT_TYPE_S = 0x01
    NOT_SUPPORT_TYPE_P = 0x02
    TRANSACTION_NOT_OPEN = 0x03
    NOT_SELECTED = 0x04

    _ITEMS = (
        NOT_SUPPORT_TYPE_S,
        NOT_SUPPORT_TYPE_P,
        TRANSACTION_NOT_OPEN,
        NOT_SELECTED
    )

    @classmethod
    def get(cls, b):
        for x in cls._ITEMS:
            if x == b:
                return x
        return cls.UNKNOWN


class HsmsSsMessage(SecsMessage):

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
                s2b = Secs2BodyBuilder.from_body_bytes(bs[14:])
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


class Secs1MessageParseError(SecsMessageParseError):

    def __init__(self, msg):
        super(Secs1MessageParseError, self).__init__(msg)


class Secs1Message(SecsMessage):

    def __init__(self, strm, func, wbit, secs2body, system_bytes, device_id, rbit):
        super(Secs1Message, self).__init__(strm, func, wbit, secs2body)
        self._system_bytes = system_bytes
        self.__device_id = int(device_id)
        self.__rbit = bool(rbit)
        self.__cache_header10bytes = None
        self.__cache_str = None
        self.__cache_repr = None
        self.__cache_blocks = None

    def __str__(self):
        if self.__cache_str is None:
            vv = [
                self._header10bytes_str(),
                self._STR_LINESEPARATOR,
                'S', str(self.strm),
                'F', str(self.func)
            ]
            if self.wbit:
                vv.append(' W')
            if self.secs2body is not None:
                vv.append(self._STR_LINESEPARATOR)
                vv.append(self.secs2body.to_sml())
            vv.append('.')
            self.__cache_str = ''.join(vv)
        return self.__cache_str

    def __repr__(self):
        if self.__cache_repr is None:
            vv = [
                "{'header':", str(self._header10bytes()),
                ",'strm':", str(self.strm),
                ",'func':", str(self.func),
                ",'wbit':", str(self.wbit)
            ]
            if self.secs2body is not None:
                vv.append(",'secs2body':")
                vv.append(repr(self.secs2body))
            vv.append("}")
            self.__cache_repr = ''.join(vv)
        return self.__cache_repr

    def _header10bytes(self):
        if self.__cache_header10bytes is None:
            b0 = (self.device_id >> 8) & 0x7F
            if self.rbit:
                b0 |= 0x80
            b1 = self.device_id & 0xFF
            b2 = self.strm & 0x7F
            if self.wbit:
                b2 |= 0x80
            b3 = self.func & 0xFF
            self.__cache_header10bytes = bytes([
                b0, b1,
                b2, b3,
                0x00, 0x00,
                self._system_bytes[0], self._system_bytes[1],
                self._system_bytes[2], self._system_bytes[3]
            ])
        return self.__cache_header10bytes

    def _device_id(self):
        return self.__device_id

    @property
    def rbit(self):
        pass

    @rbit.getter
    def rbit(self):
        return self.__rbit

    def to_blocks(self):

        def _bb(bs, from_pos):
            m = len(bs)
            x = m - from_pos
            if x > 244:
                return (bs[from_pos:(from_pos + 244)], 244, False)
            else:
                return (bs[from_pos:m], x, True)

        def _hh(hh, num, ebit):
            b4 = (num >> 8) & 0x7F
            if ebit:
                b4 |= 0x80
            b5 = num & 0xFF
            return bytes([
                hh[0], hh[1], hh[2], hh[3],
                b4, b5,
                hh[6], hh[7], hh[8], hh[9]
            ])

        def _sum(hh, bb):
            x = sum([i for i in hh]) + sum([i for i in bb])
            return bytes([((x >> 8) & 0xFF), (x & 0xFF)])

        if self.__cache_blocks is None:

            h10bs = self._header10bytes()
            if self.secs2body is None:
                bodybs = bytes()
            else:
                bodybs = self.secs2body.to_bytes()

            blocks = []
            pos = 0
            block_num = 0

            while True:
                block_num += 1

                if block_num > 0x7FFF:
                    raise Secs1MessageParseError("blocks overflow")

                bb, shift, ebit = _bb(bodybs, pos)
                hh = _hh(h10bs, block_num, ebit)
                ss = _sum(hh, bb)

                v = Secs1MessageBlock(bytes([shift + 10]) + hh + bb + ss)
                blocks.append(v)

                if ebit:
                    break

                pos += shift

            self.__cache_blocks = tuple(blocks)

        return self.__cache_blocks

    @classmethod
    def from_blocks(cls, blocks):

        if blocks is None or len(blocks) == 0:
            raise Secs1MessageParseError("No blocks")

        bs = b''.join([(x.to_bytes())[11:-2] for x in blocks])

        v = Secs1Message(
            blocks[0].strm,
            blocks[0].func,
            blocks[0].has_wbit(),
            Secs2BodyBuilder.from_body_bytes(bs) if len(bs) > 0 else None,
            blocks[0].get_system_bytes(),
            blocks[0].device_id,
            blocks[0].rbit
        )
        v.__cache_blocks = blocks
        return v


class Secs1MessageBlock():

    def __init__(self, block_bytes):
        self._bytes = block_bytes
        self._cache_str = None
        self._cache_repr = None

    def __str__(self):
        if self._cache_str is None:
            self._cache_str = (
                '[' + '{:02X}'.format(self._bytes[1])
                + ' ' + '{:02X}'.format(self._bytes[2])
                + '|' + '{:02X}'.format(self._bytes[3])
                + ' ' + '{:02X}'.format(self._bytes[4])
                + '|' + '{:02X}'.format(self._bytes[5])
                + ' ' + '{:02X}'.format(self._bytes[6])
                + '|' + '{:02X}'.format(self._bytes[7])
                + ' ' + '{:02X}'.format(self._bytes[8])
                + ' ' + '{:02X}'.format(self._bytes[9])
                + ' ' + '{:02X}'.format(self._bytes[10])
                + '] length: ' + str(self._bytes[0])
                )
        return self._cache_str

    def __repr__(self):
        if self._cache_repr is None:
            self._cache_repr = str(self._bytes)
        return self._cache_repr

    def to_bytes(self):
        return self._bytes

    @property
    def device_id(self):
        pass

    @device_id.getter
    def device_id(self):
        """Device-ID getter

        Returns:
            int: Device-ID
        """
        bs = self._bytes[1:3]
        return ((bs[0] << 8) & 0x7F00) | bs[1]

    @property
    def strm(self):
        pass

    @strm.getter
    def strm(self):
        """Stream-Number getter.

        Returns:
            int: Stream-Number
        """
        return self._bytes[3] & 0x7F

    @property
    def func(self):
        pass

    @func.getter
    def func(self):
        """Function-Number getter.

        Returns:
            int: Function-Number
        """
        return self._bytes[4]

    @property
    def rbit(self):
        pass

    @rbit.getter
    def rbit(self):
        """R-Bit getter

        Returns:
            bool: True if has R-Bit
        """
        return (self._bytes[1] & 0x80) == 0x80

    @property
    def wbit(self):
        pass

    @wbit.getter
    def wbit(self):
        """W-Bit getter

        Returns:
            bool: True if has W-Bit
        """
        return (self._bytes[3] & 0x80) == 0x80

    @property
    def ebit(self):
        pass

    @ebit.getter
    def ebit(self):
        """E-Bit getter.

        Returns:
            bool: True if has E-Bit
        """
        return (self._bytes[5] & 0x80) == 0x80

    def get_block_number(self):
        bs = self._bytes[5:7]
        return ((bs[0] << 8) & 0x7F00) | bs[1]

    def get_system_bytes(self):
        return self._bytes[7:11]

    def is_next_block(self, block):
        return (
            block._bytes[1] == self._bytes[1]
            and block._bytes[2] == self._bytes[2]
            and block._bytes[3] == self._bytes[3]
            and block._bytes[4] == self._bytes[4]
            and block._bytes[7] == self._bytes[7]
            and block._bytes[8] == self._bytes[8]
            and block._bytes[9] == self._bytes[9]
            and block._bytes[10] == self._bytes[10]
            and block.get_block_number() == (self.get_block_number() + 1)
        )


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

        self.__gem = Gem(self)

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
        strm, func, wbit, s2b = SmlParser.parse(sml_str)
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
        strm, func, wbit, s2b = SmlParser.parse(sml_str)
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
        elif isinstance(v, AbstractSecs2Body):
            return v
        else:
            tt = type(v)
            if (tt is list or tt is tuple) and len(v) == 2:
                return Secs2BodyBuilder.build(v[0], v[1])
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


class HsmsSsCommunicatorError(SecsCommunicatorError):

    def __init__(self, msg):
        super(HsmsSsCommunicatorError, self).__init__(msg)


class HsmsSsSendMessageError(SecsSendMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsSendMessageError, self).__init__(msg, ref_msg)


class HsmsSsWaitReplyMessageError(SecsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsWaitReplyMessageError, self).__init__(msg, ref_msg)


class HsmsSsTimeoutT3Error(HsmsSsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsTimeoutT3Error, self).__init__(msg, ref_msg)


class HsmsSsTimeoutT6Error(HsmsSsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsTimeoutT6Error, self).__init__(msg, ref_msg)


class HsmsSsRejectMessageError(HsmsSsWaitReplyMessageError):

    def __init__(self, ref_msg):
        super(HsmsSsRejectMessageError, self).__init__('Reject', ref_msg)


class HsmsSsCommunicateState:

    NOT_CONNECT = 'not_connect'
    CONNECTED = 'connected'
    SELECTED = 'selected'


class HsmsSsConnection:

    def __init__(self, sock, parent, recv_primary_msg_callback):
        self._sock = sock
        self._parent = parent
        self._rpm_cb = recv_primary_msg_callback

        self._tpe = concurrent.futures.ThreadPoolExecutor(max_workers=32)
        self._closed = False

        self._rsp_pool = dict()
        self._rsp_pool_lock = threading.Lock()
        self._rsp_pool_cdt = threading.Condition()

        self._send_lock = threading.Lock()

        self._recv_all_msg_putter = CallbackQueuing(parent._put_recv_all_msg)
        self._sended_msg_putter = CallbackQueuing(parent._put_sended_msg)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def open(self):

        self._recv_all_msg_putter.open()
        self._sended_msg_putter.open()

        def _f():

            with (
                CallbackQueuing(self._rpm_cb) as pmq,
                PutListQueuing() as llq):

                def _recv_bytes():

                    while not self._closed:

                        try:

                            heads = list()
                            pos = 0
                            size = 14

                            r = llq.put_to_list(heads, pos, size)
                            if r < 0:
                                return None

                            pos += r

                            while pos < size:
                                r = llq.put_to_list(heads, pos, size, self._parent.timeout_t8)
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
                                r = llq.put_to_list(bodys, pos, size, self._parent.timeout_t8)
                                if r < 0:
                                    raise HsmsSsCommunicatorError("T8-Timeout")
                                else:
                                    pos += r

                            msg = HsmsSsMessage.from_bytes(bytes(heads) + bytes(bodys))
                            key = msg.get_system_bytes()

                            self._recv_all_msg_putter.put(msg)

                            with self._rsp_pool_lock:
                                if key in self._rsp_pool:
                                    self._rsp_pool[key] = msg
                                    with self._rsp_pool_cdt:
                                        self._rsp_pool_cdt.notify_all()
                                else:
                                    pmq.put(msg)

                        except HsmsSsCommunicatorError as e:
                            self._parent._put_error(e)

                self._tpe.submit(_recv_bytes)

                try :
                    while not self._closed:
                        bs = self._sock.recv(4096)
                        if bs:
                            llq.puts(bs)
                        else:
                            self._parent._put_error(HsmsSsCommunicatorError("Terminate detect"))
                            break

                except Exception as e:
                    if not self._closed:
                        self._parent._put_error(HsmsSsCommunicatorError(e))

        self._tpe.submit(_f)

    def close(self):
        self._closed = True

        self._sended_msg_putter.close()
        self._recv_all_msg_putter.close()

        with self._rsp_pool_cdt:
            self._rsp_pool_cdt.notify_all()

        self._tpe.shutdown(wait=True, cancel_futures=True)

    def send(self, msg):

        timeout_tx = -1.0

        ctrl_type = msg.get_control_type()
        if ctrl_type == HsmsSsControlType.DATA:
            if msg.has_wbit():
                timeout_tx = self._parent.timeout_t3
        elif (ctrl_type == HsmsSsControlType.SELECT_REQ
            or ctrl_type == HsmsSsControlType.LINKTEST_REQ):
            timeout_tx = self._parent.timeout_t6

        def _send(msg):
            with self._send_lock:
                try:
                    self._sock.sendall(msg.to_bytes())
                    self._sended_msg_putter.put(msg)
                except Exception as e:
                    raise HsmsSsSendMessageError(e, msg)

        if timeout_tx > 0.0:

            key = msg.get_system_bytes()

            try:
                with self._rsp_pool_lock:
                    self._rsp_pool[key] = None

                _send(msg)

                def _f():
                    while True:
                        with self._rsp_pool_lock:
                            if key in self._rsp_pool:
                                rsp = self._rsp_pool[key]
                                if rsp is not None:
                                    return rsp
                            else:
                                return None
                        with self._rsp_pool_cdt:
                            self._rsp_pool_cdt.wait()

                f = self._tpe.submit(_f)

                try:
                    r = f.result(timeout_tx)

                    if r.get_control_type() == HsmsSsControlType.REJECT_REQ:
                        raise HsmsSsRejectMessageError(msg)

                    return r

                except concurrent.futures.TimeoutError as e:

                    if ctrl_type == HsmsSsControlType.DATA:
                        raise HsmsSsTimeoutT3Error(e, msg)
                    else:
                        raise HsmsSsTimeoutT6Error(e, msg)

            finally:
                with self._rsp_pool_lock:
                    del self._rsp_pool[key]

        else:
            _send(msg)
            return None


class AbstractHsmsSsCommunicator(AbstractSecsCommunicator):

    def __init__(self, session_id, is_equip, **kwargs):
        super(AbstractHsmsSsCommunicator, self).__init__(session_id, is_equip, **kwargs)
        self._hsmsss_connection = None

        self._hsmsss_connection_rlock = threading.RLock()

        self._hsmsss_comm_rlock = threading.RLock()
        self._hsmsss_comm = HsmsSsCommunicateState.NOT_CONNECT

        self._hsmsss_comm_lstnrs = list()

        hsmssscomml = kwargs.get('hsmsss_communicate', None)
        if hsmssscomml is not None:
            self.add_hsmsss_communicate_listener(hsmssscomml)

    def __str__(self):
        ipaddr = self.get_ipaddress()
        return (
            'protocol: ' + str(self.get_protocol())
            + ', ip-address: ' + str(ipaddr[0])
            + ':' + str(ipaddr[1])
            + ', session-id: ' + str(self._dev_id)
            + ', is-equip: ' + str(self._is_equip)
            + ', communicate-state: ' + self.get_hsmsss_communicate_state()
            + ', name: ' + self.get_name()
            )

    def __repr__(self):
        return (
            '{protocol:' + repr(self.get_protocol())
            + ',ipaddr:' + repr(self.get_ipaddress())
            + ',sessionid:' + repr(self._dev_id)
            + ',isequip:' + repr(self._is_equip)
            + ',communicatestate:' + repr(self.get_hsmsss_communicate_state())
            + ',name:' + repr(self.get_name())
            + '}'
            )

    def get_protocol(self):
        return None

    def get_ipaddress(self):
        return (None, None)

    def _close(self):
        with self._open_close_rlock:
            if self.is_closed():
                return
            self._set_closed()

    def _set_hsmsss_connection(self, conn, callback=None):
        with self._hsmsss_connection_rlock:
            if self._hsmsss_connection is None:
                self._hsmsss_connection = conn
                if callback is not None:
                    callback()
                return True
            else:
                return False

    def _unset_hsmsss_connection(self, callback=None):
        with self._hsmsss_connection_rlock:
            self._hsmsss_connection = None
            if callback is not None:
                callback()

    def _send(self, strm, func, wbit, secs2body, system_bytes, device_id):
        return self.send_hsmsss_msg(
            HsmsSsDataMessage(strm, func, wbit, secs2body, system_bytes, device_id))

    def send_hsmsss_msg(self, msg):
        def _f():
            with self._hsmsss_connection_rlock:
                if self._hsmsss_connection is None:
                    raise HsmsSsSendMessageError("HsmsSsCommunicator not connected", msg)
                else:
                    return self._hsmsss_connection
        return _f().send(msg)

    def build_select_req(self):
        return HsmsSsControlMessage.build_select_request(self._create_system_bytes())

    def send_select_req(self):
        return self.send_hsmsss_msg(self.build_select_req())

    def send_select_rsp(self, primary, status):
        return self.send_hsmsss_msg(
            HsmsSsControlMessage.build_select_response(primary, status))

    def send_linktest_req(self):
        return self.send_hsmsss_msg(
            HsmsSsControlMessage.build_linktest_request(self._create_system_bytes()))

    def send_linktest_rsp(self, primary):
        return self.send_hsmsss_msg(
            HsmsSsControlMessage.build_linktest_response(primary))

    def send_reject_req(self, primary, reason):
        return self.send_hsmsss_msg(
            HsmsSsControlMessage.build_reject_request(primary, reason))

    def send_separate_req(self):
        return self.send_hsmsss_msg(
            HsmsSsControlMessage.build_separate_request(self._create_system_bytes()))


    def get_hsmsss_communicate_state(self):
        with self._hsmsss_comm_rlock:
            return self._hsmsss_comm

    def add_hsmsss_communicate_listener(self, l):
        with self._hsmsss_comm_rlock:
            self._hsmsss_comm_lstnrs.append(l)
            l(self._hsmsss_comm, self)

    def remove_hsmsss_communicate_listener(self, l):
        with self._hsmsss_comm_rlock:
            self._hsmsss_comm_lstnrs.remove(l)

    def _put_hsmsss_comm_state(self, state, callback=None):
        with self._hsmsss_comm_rlock:
            if state != self._hsmsss_comm:
                self._hsmsss_comm = state
                for lstnr in self._hsmsss_comm_lstnrs:
                    lstnr(self._hsmsss_comm, self)
                self._put_communicated(state == HsmsSsCommunicateState.SELECTED)
                if callback is not None:
                    callback()

    def _put_hsmsss_comm_state_to_not_connected(self, callback=None):
        self._put_hsmsss_comm_state(HsmsSsCommunicateState.NOT_CONNECT, callback)

    def _put_hsmsss_comm_state_to_connected(self, callback=None):
        self._put_hsmsss_comm_state(HsmsSsCommunicateState.CONNECTED, callback)

    def _put_hsmsss_comm_state_to_selected(self, callback=None):
        self._put_hsmsss_comm_state(HsmsSsCommunicateState.SELECTED, callback)


class HsmsSsActiveCommunicator(AbstractHsmsSsCommunicator):

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

        self._waiting_cdt = threading.Condition()
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

            with CallbackQueuing(self._put_recv_primary_msg) as pq:

                while self.is_open:

                    try:

                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

                            sock.connect(self.get_ipaddress())

                            def _recv(msg):

                                if msg is None:
                                    with self._waiting_cdt:
                                        self._waiting_cdt.notify_all()
                                    return

                                ctrl_type = msg.get_control_type()

                                try:
                                    if ctrl_type == HsmsSsControlType.DATA:

                                        if self.get_hsmsss_communicate_state() == HsmsSsCommunicateState.SELECTED:
                                            pq.put(msg)
                                        else:
                                            self.send_reject_req(msg, HsmsSsRejectReason.NOT_SELECTED)

                                    elif ctrl_type == HsmsSsControlType.LINKTEST_REQ:

                                        self.send_linktest_rsp(msg)

                                    elif ctrl_type == HsmsSsControlType.SEPARATE_REQ:

                                        with self._waiting_cdt:
                                            self._waiting_cdt.notify_all()

                                    elif ctrl_type == HsmsSsControlType.SELECT_REQ:
                                        self.send_reject_req(msg, HsmsSsRejectReason.NOT_SUPPORT_TYPE_S)

                                    elif (ctrl_type == HsmsSsControlType.SELECT_RSP
                                        or ctrl_type == HsmsSsControlType.LINKTEST_RSP):

                                        self.send_reject_req(msg, HsmsSsRejectReason.TRANSACTION_NOT_OPEN)

                                    elif ctrl_type == HsmsSsControlType.REJECT_REQ:

                                        # Nothing
                                        pass

                                    else:

                                        if HsmsSsControlType.has_s_type(msg.get_s_type()):
                                            self.send_reject_req(msg, HsmsSsRejectReason.NOT_SUPPORT_TYPE_P)
                                        else:
                                            self.send_reject_req(msg, HsmsSsRejectReason.NOT_SUPPORT_TYPE_S)

                                except HsmsSsCommunicatorError as e:
                                    self._put_error(e)
                                except HsmsSsSendMessageError as e:
                                    self._put_error(e)

                            with HsmsSsConnection(sock, self, _recv) as conn:

                                try:
                                    self._put_hsmsss_comm_state_to_connected()

                                    rsp = conn.send(self.build_select_req())

                                    if rsp is not None:

                                        if rsp.get_control_type() == HsmsSsControlType.SELECT_RSP:

                                            ss = rsp.get_select_status()

                                            if (ss == HsmsSsSelectStatus.SUCCESS
                                                or ss == HsmsSsSelectStatus.ACTIVED):

                                                self._set_hsmsss_connection(
                                                    conn,
                                                    self._put_hsmsss_comm_state_to_selected)

                                                with self._waiting_cdt:
                                                    self._waiting_cdt.wait()

                                finally:
                                    self._unset_hsmsss_connection(self._put_hsmsss_comm_state_to_not_connected)

                                    try:
                                        sock.shutdown(socket.SHUT_RDWR)
                                    except Exception:
                                        pass

                    except ConnectionError as e:
                        self._put_error(HsmsSsCommunicatorError(e))
                    except HsmsSsCommunicatorError as e:
                        self._put_error(e)
                    except HsmsSsSendMessageError as e:
                        self._put_error(e)
                    except HsmsSsWaitReplyError as e:
                        self._put_error(e)
                    finally:
                        self._put_hsmsss_comm_state_to_not_connected()

                    if self.is_closed:
                        return None

                    with self._waiting_cdt:
                        self._waiting_cdt.wait(self.timeout_t5)

        self.__tpe.submit(_f)

    def _close(self):

        with self.__open_close_local_lock:
            if self.is_closed:
                return
            self._set_closed()

        with self._waiting_cdt:
            self._waiting_cdt.notify_all()

        self.__tpe.shutdown(wait=True, cancel_futures=True)


class HsmsSsPassiveCommunicator(AbstractHsmsSsCommunicator):

    _PROTOCOL_NAME = 'HSMS-SS-PASSIVE'

    def __init__(self, ip_address, port, session_id, is_equip, **kwargs):
        super(HsmsSsPassiveCommunicator, self).__init__(session_id, is_equip, **kwargs)
        self._tpe = concurrent.futures.ThreadPoolExecutor(max_workers=64)
        self._ipaddr = (ip_address, port)

        self._waiting_cdts = list()
        self.__open_close_local_lock = threading.Lock()

    def get_protocol(self):
        return self._PROTOCOL_NAME

    def get_ipaddress(self):
        return self._ipaddr

    def _open(self):

        with self.__open_close_local_lock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
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
                            while not self.is_closed:

                                sock = (server.accept())[0]

                                def _ff():
                                    self._accept_socket(sock)

                                self._tpe.submit(_ff)

                        except Exception as e:
                            if self.is_open:
                                self._put_error(HsmsSsCommunicatorError(e))

                    self._tpe.submit(_f)

                    self._waiting_cdts.append(cdt)
                    with cdt:
                        cdt.wait()

            except Exception as e:
                if self.is_open:
                    self._put_error(HsmsSsCommunicatorError(e))

        self._tpe.submit(_open_server)

    def _accept_socket(self, sock):

        with (
            CallbackQueuing(self._put_recv_primary_msg) as pq,
            WaitingQueuing() as wq,
            HsmsSsConnection(sock, self, wq.put) as conn):

            cdt = threading.Condition()

            def _f():

                try:

                    while self.is_open:

                        msg = wq.poll(self.timeout_t7)

                        if msg is None:
                            raise HsmsSsCommunicatorError("T7-Timeout")

                        ctrl_type = msg.get_control_type()

                        if ctrl_type == HsmsSsControlType.SELECT_REQ:

                            if self._set_hsmsss_connection(conn):

                                conn.send(HsmsSsControlMessage.build_select_response(
                                    msg,
                                    HsmsSsSelectStatus.SUCCESS))

                                break

                            else:

                                conn.send(HsmsSsControlMessage.build_select_response(
                                    msg,
                                    HsmsSsSelectStatus.ALREADY_USED))

                        elif ctrl_type == HsmsSsControlType.LINKTEST_REQ:

                            conn.send(HsmsSsControlMessage.build_linktest_response(msg))

                        elif ctrl_type == HsmsSsControlType.DATA:

                            conn.send(HsmsSsControlMessage.build_reject_request(
                                msg,
                                HsmsSsRejectReason.NOT_SELECTED))

                        elif ctrl_type == HsmsSsControlType.SEPARATE_REQ:

                            return None

                        elif (ctrl_type == HsmsSsControlType.SELECT_RSP
                            or ctrl_type == HsmsSsControlType.LINKTEST_RSP):

                            conn.send(HsmsSsControlMessage.build_reject_request(
                                msg,
                                HsmsSsRejectReason.TRANSACTION_NOT_OPEN))

                        elif ctrl_type == HsmsSsControlType.REJECT_REQ:

                            #Nothing
                            pass

                        else:

                            if HsmsSsControlType.has_s_type(msg.get_s_type()):

                                conn.send(HsmsSsControlMessage.build_reject_request(
                                    msg,
                                    HsmsSsRejectReason.NOT_SUPPORT_TYPE_P))

                            else:

                                conn.send(HsmsSsControlMessage.build_reject_request(
                                    msg,
                                    HsmsSsRejectReason.NOT_SUPPORT_TYPE_S))

                    try:
                        self._put_hsmsss_comm_state_to_selected()

                        while True:

                            msg = wq.poll()

                            if msg is None:
                                raise HsmsSsCommunicatorError("Terminate detect")

                            ctrl_type = msg.get_control_type()

                            if ctrl_type == HsmsSsControlType.DATA:

                                pq.put(msg)

                            elif ctrl_type == HsmsSsControlType.LINKTEST_REQ:

                                self.send_linktest_rsp(msg)

                            elif ctrl_type == HsmsSsControlType.SELECT_REQ:

                                self.send_select_rsp(msg, HsmsSsSelectStatus.ACTIVED)

                            elif ctrl_type == HsmsSsControlType.SEPARATE_REQ:

                                return None

                            elif (ctrl_type == HsmsSsControlType.SELECT_RSP
                                or ctrl_type == HsmsSsControlType.LINKTEST_RSP):

                                self.send_reject_req(msg, HsmsSsRejectReason.TRANSACTION_NOT_OPEN)

                            elif ctrl_type == HsmsSsControlType.REJECT_REQ:

                                #Nothing
                                pass

                            else:

                                if HsmsSsControlType.has_s_type(msg.get_s_type()):
                                    self.send_reject_req(msg, HsmsSsRejectReason.NOT_SUPPORT_TYPE_P)
                                else:
                                    self.send_reject_req(msg, HsmsSsRejectReason.NOT_SUPPORT_TYPE_S)

                    finally:
                        self._unset_hsmsss_connection(self._put_hsmsss_comm_state_to_not_connected)

                except HsmsSsCommunicatorError as e:
                    if self.is_open:
                        self._put_error(e)
                except HsmsSsSendMessageError as e:
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

        with self.__open_close_local_lock:
            if self.is_closed:
                return
            self._set_closed()

        for cdt in self._waiting_cdts:
            with cdt:
                cdt.notify_all()

        self._tpe.shutdown(wait=True, cancel_futures=True)


class AbstractSecs1Communicator(AbstractSecsCommunicator):

    _DEFAULT_RETRY = 3

    def __init__(self, session_id, is_equip, is_master, **kwargs):
        super(AbstractSecs1Communicator, self).__init__(session_id, is_equip, **kwargs)
        self.set_master_mode(is_master)
        self.set_retry(kwargs.get('retry', self._DEFAULT_RETRY))

    def set_master_mode(self, is_master):
        self._is_master = bool(is_master)

    def set_retry(self, v):
        if v is None:
            raise TypeError("retry-value require not None")
        if v >= 0:
            self._retry = v
        else:
            raise ValueError("retry-value require >= 0")

    def _open(self):
        pass

    def _close(self):
        with self._open_close_rlock:
            if self.is_closed():
                return
            self._set_closed()

    def _send(self, strm, func, wbit, secs2body, system_bytes, device_id):
        return self.send_secs1_msg(
            Secs1Message(strm, func, wbit, secs2body, system_bytes, device_id, self._is_equip))

    def send_secs1_msg(self, msg):

        timeout_tx = self._timeout_t3 if msg.has_wbit() else -1.0

        #TODO
        #send

        if timeout_tx > 0.0:

            #TODO
            #wait-reply
            return 1

        else:
            return None


class ClockType:
    A12 = 'A12'
    A16 = 'A16'


class COMMACK:
    OK = 0x0
    DENIED = 0x1


class OFLACK:
    OK = 0x0


class ONLACK:
    OK = 0x0
    REFUSE = 0x1
    ALREADY_ONLINE = 0x2


class Gem:

    __DEFAULT_MDLN = '      '
    __DEFAULT_SOFTREV = '      '
    __DEFAULT_CLOCK_TYPE = ClockType.A16

    def __init__(self, comm):
        self._comm = comm
        self.mdln = self.__DEFAULT_MDLN
        self.softrev = self.__DEFAULT_SOFTREV
        self.clock_type = self.__DEFAULT_CLOCK_TYPE

    @property
    def mdln(self):
        pass

    @mdln.setter
    def mdln(self, val):
        self.__mdln = str(val)

    @mdln.getter
    def mdln(self):
        return self.__mdln

    @property
    def softrev(self):
        pass

    @softrev.setter
    def softrev(self, val):
        self.__softrev = str(val)

    @softrev.getter
    def softrev(self):
        return self.__softrev

    @property
    def clock_type(self):
        pass

    @clock_type.setter
    def clock_type(self, val):
        self.__clock_type = val

    @clock_type.getter
    def clock_type(self):
        return self.__clock_type

    def s1f13(self):
        if self._comm.is_equip:

            return self._comm.send(
                1, 13, True,
                ('L', [
                    ('A', self.mdln),
                    ('A', self.softrev)
                ])
            ).secs2body[0][0]

        else:

            return self._comm.send(
                1, 13, True,
                ('L', [])
            ).secs2body[0][0]

    def s1f14(self, primary_msg, commack):
        if self._comm.is_equip:

            return self._comm.reply(
                primary_msg,
                1, 14, False,
                ('L', [
                    ('B', [commack]),
                    ('L', [
                        ('A', self.mdln),
                        ('A', self.softrev)
                    ])
                ])
            )

        else:

            return self._comm.reply(
                primary_msg,
                1, 14, False,
                ('L', [
                    ('B', [commack]),
                    ('L', [])
                ])
            )

    def s1f15(self):
        return self._comm.send(1, 15, True).secs2body[0]

    def s1f16(self, primary_msg):
        return self._comm.reply(
            primary_msg,
            1, 16, False,
            ('B', [OFLACK.OK])
        )

    def s1f17(self):
        return self._comm.send(1, 17, True).secs2body[0]

    def s1f18(self, primary_msg, onlack):
        return self._comm.reply(
            primary_msg,
            1, 18, False,
            ('B', [onlack])
        )

    def __s9fy(self, ref_msg, func):
        return self._comm.send(
            9, func, False,
            ('B', ref_msg._header10bytes())
        )

    def s9f1(self, ref_msg):
        """S9F1, Unknown Device ID.

        Args:
            ref_msg (<SecsMessage>): Reference-Message

        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.

        Returns:
            None: None
        """
        return self.__s9fy(ref_msg, 1)

    def s9f3(self, ref_msg):
        """S9F3, Unknown Stream.

        Args:
            ref_msg (<SecsMessage>): Reference-Message

        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.

        Returns:
            None: None
        """
        return self.__s9fy(ref_msg, 3)

    def s9f5(self, ref_msg):
        """S9F5, Unknown Function.

        Args:
            ref_msg (<SecsMessage>): Reference-Message

        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.

        Returns:
            None: None
        """
        self.__s9fy(ref_msg, 5)

    def s9f7(self, ref_msg):
        """S9F7, Illegal Data.

        Args:
            ref_msg (<SecsMessage>): Reference-Message

        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.

        Returns:
            None: None
        """
        return self.__s9fy(ref_msg, 7)

    def s9f9(self, ref_msg):
        """S9F9, Transaction Timeout.

        Args:
            ref_msg (<SecsMessage>): Reference-Message

        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.

        Returns:
            None: None
        """
        return self.__s9fy(ref_msg, 9)

    def s9f11(self, ref_msg):
        """S9F11, Data Too Long.

        Args:
            ref_msg (<SecsMessage>): Reference-Message

        Raises:
            SecsCommunicatorError: if communicator not opened.
            SecsSendMessageError: if send failed.

        Returns:
            None: None
        """
        return self.__s9fy(ref_msg, 11)


if __name__ == '__main__':
    print('write here')

