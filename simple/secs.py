import os
import importlib
import socket
import re
import struct
import threading
import datetime


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
        self.__cache_sml = None
        self.__cache_repr = None
        self.__cache_bytes = None

    def __str__(self):
        return self.to_sml()

    def __repr__(self):
        if self.__cache_repr is None:
            self.__cache_repr = str((self._type[0], self._value))
        return self.__cache_repr

    def __len__(self):
        return len(self._value)

    def __getitem__(self, item):
        try:
            return self._value[item]
        except IndexError as e:
            raise Secs2BodyParseError(e)

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

        Raises:
            Secs2BodyParseError: if IndexError or TypeError.

        Returns:
            str: 'L', 'A', 'BOOLEAN', 'B', 'I1', 'I2', 'I4', 'I8', 'U1', 'U2', 'U4', 'U8', 'F4', 'F8'
        """
        try:
            v = self
            for i in indices:
                v = v[i]

            return v._type[0]

        except IndexError as e:
            raise Secs2BodyParseError(e)
        except TypeError as e:
            raise Secs2BodyParseError(e)

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

        Raises:
            Secs2BodyParseError: if IndexError or TypeError.

        Returns:
            Any: seek value.
        """
        try:
            v = self
            for i in indices:
                v = v[i]

        except IndexError as e:
            raise Secs2BodyParseError(e)
        except TypeError as e:
            raise Secs2BodyParseError(e)

        if isinstance(v, AbstractSecs2Body):
            return v._value
        else:
            return v

    def to_sml(self):
        """SML getter.

        Returns:
            str: SML
        """
        if self.__cache_sml is None:
            self.__cache_sml = self._create_to_sml()
        return self.__cache_sml

    def to_bytes(self):
        """bytes getter.

        Returns:
            bytes: bytes
        """
        if self.__cache_bytes is None:
            self.__cache_bytes = self._create_to_bytes()
        return self.__cache_bytes

    def _create_to_sml(self):
        l, v = self._create_to_sml_value()
        return '<' + self._type[0] + ' [' + str(l) + '] ' + str(v) + ' >'

    def _create_to_sml_value(self):
        return 0, ''

    def _create_to_bytes(self):
        bs_vv = self._create_to_bytes_value()
        v_len = len(bs_vv)
        bs_len = struct.pack('>L', v_len)
        if v_len >= self._BYTES_LEN_3:
            return struct.pack('>B', (self._type[1] | 0x03)) + bs_len[1:4] + bs_vv
        elif v_len >= self._BYTES_LEN_2:
            return struct.pack('>B', (self._type[1] | 0x02)) + bs_len[2:4] + bs_vv
        else:
            return struct.pack('>B', (self._type[1] | 0x01)) + bs_len[3:4] + bs_vv

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
        v_max = x-1

        if is_signed:
            v_min = -x
        else:
            v_min = 0

        if v > v_max or v < v_min:
            raise ValueError("value is from " + str(min) + " to " + str(max) + ", value is " + str(v))

        return v


class Secs2AsciiBody(AbstractSecs2Body):

    def __init__(self, item_type, value):
        super(Secs2AsciiBody, self).__init__(item_type, str(value))

    def _create_to_sml_value(self):
        return len(self._value), ('"' + self._value + '"')

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
        return len(vv), self._SML_VALUESEPARATOR.join(vv)

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
        return len(vv), self._SML_VALUESEPARATOR.join(vv)

    @staticmethod
    def build(item_type, value):
        return Secs2BinaryBody(item_type, value)


class AbstractSecs2NumberBody(AbstractSecs2Body):

    def __init__(self, item_type, value):
        super(AbstractSecs2NumberBody, self).__init__(item_type, tuple(value))

    def _create_to_sml_value(self):
        vv = [str(x) for x in self._value]
        return len(vv), self._SML_VALUESEPARATOR.join(vv)

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
                if x.type == 'L':
                    vv.append(_lsf(x.value, deep_level))
                else:
                    vv.append(deep_level + x.to_sml())
            vv.append(level + '>')
            return self._SML_LINESEPARATOR.join(vv)

        return _lsf(self._value)

    def _create_to_bytes(self):
        v_len = len(self._value)
        bs_len = struct.pack('>L', v_len)
        bs_vv = b''.join([x.to_bytes() for x in self._value])
        if v_len >= self._BYTES_LEN_3:
            return struct.pack('>B', (self._type[1] | 0x03)) + bs_len[1:4] + bs_vv
        elif v_len >= self._BYTES_LEN_2:
            return struct.pack('>B', (self._type[1] | 0x02)) + bs_len[2:4] + bs_vv
        else:
            return struct.pack('>B', (self._type[1] | 0x01)) + bs_len[3:4] + bs_vv

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
                len_bs = (bs[pos+1] << 16) | (bs[pos+2] << 8) | bs[pos+3]
            elif len_bit == 2:
                len_bs = (bs[pos+1] << 8) | bs[pos+2]
            else:
                len_bs = bs[pos+1]

            return t, len_bs, (len_bit + 1)

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
                return tt[5](tt, vv), p

            elif tt[0] == 'BOOLEAN':
                vv = [(b != 0x00) for b in bs[start_index:end_index]]
                return tt[5](tt, vv), end_index

            elif tt[0] == 'A':
                v = bs[start_index:end_index].decode(encoding='ascii')
                return tt[5](tt, v), end_index

            elif tt[0] == 'B':
                vv = bs[start_index:end_index]
                return tt[5](tt, vv), end_index

            elif tt[0] in ('I1', 'I2', 'I4', 'I8', 'F8', 'F4', 'U1', 'U2', 'U4', 'U8'):
                vv = list()
                p = start_index
                for _ in range(0, v_len, tt[2]):
                    prev = p
                    p += tt[2]
                    v = struct.unpack(('>' + tt[3]), bs[prev:p])
                    vv.append(v[0])
                return tt[5](tt, vv), end_index

        try:
            if len(body_bytes) == 0:
                return None

            lr, lp = _f(body_bytes, 0)
            len_body = len(body_bytes)

            if lp == len_body:
                lr._cache_bytes = bytes(body_bytes)
                return lr
            else:
                raise Secs2BodyBytesParseError("not reach bytes end, reach=" + str(lp) + ", length=" + str(len_body))

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
                                return v, p
                        else:
                            if a(v):
                                return v, p
                    p += 1
            else:
                while True:
                    v = s[p]
                    if _is_ws(v):
                        p += 1
                    else:
                        return v, p

        def _ssbkt(s, from_pos):    # seek size_start_bracket'[' position, return position, -1 if not exist
            v, p = _seek_next(s, from_pos)
            return p if v == '[' else -1

        def _sebkt(s, from_pos):    # seek size_end_bracket']' position, return position
            return (_seek_next(s, from_pos, ']'))[1]

        def _isbkt(s, from_pos):    # seek item_start_bracket'<' position, return position, -1 if not exist
            v, p = _seek_next(s, from_pos)
            return p if v == '<' else -1

        def _iebkt(s, from_pos):    # seek item_end_bracket'>' position, return position
            return (_seek_next(s, from_pos, '>'))[1]

        def _seek_item(s, from_pos):  # seek item_type, return (item_type, shifted_position)
            p_start = (_seek_next(s, from_pos))[1]
            p_end = (_seek_next(s, (p_start + 1), '[', '"', '<', '>', _is_ws))[1]
            return Secs2BodyBuilder.get_item_type_from_sml(s[p_start:p_end]), p_end

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
                        return tt[5](tt, vv), (p + 1)

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
                        raise Secs2BodySmlParseError("Not accept, BOOLEAN require TRUE or FALSE")
                return tt[5](tt, vv), (r + 1)

            elif tt[0] == 'A':
                vv = list()
                while True:
                    v, p_start = _seek_next(s, p)
                    if v == '>':
                        return tt[5](tt, ''.join(vv)), (p_start + 1)

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
                return tt[5](tt, s[p:r].strip().split()), (r + 1)

        try:
            if sml_str is None:
                raise Secs2BodySmlParseError("Not accept None")

            ss = str(sml_str).strip()
            lr, lp = _f(ss, 0)
            if len(ss[lp:]) > 0:
                raise Secs2BodySmlParseError("Not reach end, end=" + str(lp) + ", length=" + str(len(ss)))
            return lr

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
        raise NotImplementedError()

    @property
    def system_bytes(self):
        pass

    @system_bytes.getter
    def system_bytes(self):
        return (self._header10bytes())[6:10]

    @property
    def header10bytes(self):
        pass

    @header10bytes.getter
    def header10bytes(self):
        return self._header10bytes()

    def _header10bytes(self):
        # prototype
        # return bytes(10)
        raise NotImplementedError()

    def get_header10bytes_str(self):

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


class HsmsSsSelectStatus:

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


class HsmsSsRejectReason:

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
            vv = [self.get_header10bytes_str(), ' length:', str(self._msg_length())]
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

    def _device_id(self):
        # prototype
        raise NotImplementedError()

    def _header10bytes(self):
        # prototype
        # return bytes(10)
        raise NotImplementedError()

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
            msg_len = self._msg_length()
            vv = [
                bytes([
                    (msg_len >> 24) & 0xFF,
                    (msg_len >> 16) & 0xFF,
                    (msg_len >> 8) & 0xFF,
                    msg_len & 0xFF
                ]),
                self._header10bytes(),
                b'' if self.secs2body is None else self.secs2body.to_bytes()
            ]
            self._cache_bytes = b''.join(vv)
        return self._cache_bytes

    @classmethod
    def from_bytes(cls, bs):

        h10bs = bs[4:14]
        sys_bs = h10bs[6:10]

        ctrl_type = HsmsSsControlType.get(h10bs[4:6])

        if ctrl_type == HsmsSsControlType.DATA:

            dev_id = (h10bs[0] << 8) | h10bs[1]
            strm = h10bs[2] & 0x7F
            func = h10bs[3]
            wbit = (h10bs[2] & 0x80) == 0x80

            if len(bs) > 14:
                s2b = Secs2BodyBuilder.from_body_bytes(bs[14:])
                v = HsmsSsDataMessage(strm, func, wbit, s2b, sys_bs, dev_id)
            else:
                v = HsmsSsDataMessage(strm, func, wbit, None, sys_bs, dev_id)

        else:

            v = HsmsSsControlMessage(sys_bs, ctrl_type)
            v._p_type = h10bs[2]
            v._s_type = h10bs[3]

        v._cache_bytes = bs
        v._cache_header10bytes = h10bs

        return v


class HsmsSsDataMessage(HsmsSsMessage):

    def __init__(self, strm, func, wbit, secs2body, system_bytes, session_id):
        super(HsmsSsDataMessage, self).__init__(strm, func, wbit, secs2body, system_bytes, HsmsSsControlType.DATA)
        self.__session_id = session_id
        self.__cache_header10bytes = None

    def _header10bytes(self):
        if self.__cache_header10bytes is None:
            b2 = self.strm
            if self.wbit:
                b2 |= 0x80

            self.__cache_header10bytes = bytes([
                (self.session_id >> 8) & 0x7F,
                self.session_id & 0xFF,
                b2, self.func,
                self._control_type[0], self._control_type[1],
                self._system_bytes[0], self._system_bytes[1],
                self._system_bytes[2], self._system_bytes[3]
                ])

        return self.__cache_header10bytes

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
        self.__cache_header10bytes = None

    CONTROL_DEVICE_ID = -1

    def _device_id(self):
        return self.CONTROL_DEVICE_ID

    def _header10bytes(self):
        if self.__cache_header10bytes is None:
            self.__cache_header10bytes = bytes([
                0xFF, 0xFF,
                0x00, 0x00,
                self._control_type[0], self._control_type[1],
                self._system_bytes[0], self._system_bytes[1],
                self._system_bytes[2], self._system_bytes[3]
                ])

        return self.__cache_header10bytes

    @classmethod
    def build_select_request(cls, system_bytes):
        return HsmsSsControlMessage(system_bytes, HsmsSsControlType.SELECT_REQ)

    @classmethod
    def build_select_response(cls, primary_msg, select_status):
        ctrl_type = HsmsSsControlType.SELECT_RSP
        sys_bytes = primary_msg.system_bytes
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
            primary_msg.system_bytes,
            HsmsSsControlType.LINKTEST_RSP)

    @classmethod
    def build_reject_request(cls, primary_msg, reject_reason):
        ctrl_type = HsmsSsControlType.REJECT_REQ
        h10bytes = primary_msg.header10bytes
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
                self.get_header10bytes_str(),
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
                return bs[from_pos:(from_pos + 244)], 244, False
            else:
                return bs[from_pos:m], x, True

        def _hh(l_hh, num, l_ebit):
            b4 = (num >> 8) & 0x7F
            if l_ebit:
                b4 |= 0x80
            b5 = num & 0xFF
            return bytes([
                l_hh[0], l_hh[1], l_hh[2], l_hh[3],
                b4, b5,
                l_hh[6], l_hh[7], l_hh[8], l_hh[9]
            ])

        def _sum(l_hh, l_bb):
            x = sum([i for i in l_hh]) + sum([i for i in l_bb])
            return bytes([((x >> 8) & 0xFF), (x & 0xFF)])

        if self.__cache_blocks is None:

            h10bs = self._header10bytes()
            if self.secs2body is None:
                body_bs = bytes()
            else:
                body_bs = self.secs2body.to_bytes()

            blocks = []
            pos = 0
            block_num = 0

            while True:
                block_num += 1

                if block_num > 0x7FFF:
                    raise Secs1MessageParseError("blocks overflow")

                bb, shift, ebit = _bb(body_bs, pos)
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

        try:
            v = Secs1Message(
                blocks[0].strm,
                blocks[0].func,
                blocks[0].wbit,
                Secs2BodyBuilder.from_body_bytes(bs) if bs else None,
                blocks[0].get_system_bytes(),
                blocks[0].device_id,
                blocks[0].rbit
            )
            v.__cache_blocks = tuple(blocks)
            return v

        except Secs2BodyParseError as e:
            raise Secs1MessageParseError(e)


class Secs1MessageBlock:

    def __init__(self, block_bytes):
        self.__bytes = block_bytes
        self.__cache_str = None
        self.__cache_repr = None

    def __str__(self):
        if self.__cache_str is None:
            self._cache_str = (
                '[' + '{:02X}'.format(self.__bytes[1])
                + ' ' + '{:02X}'.format(self.__bytes[2])
                + '|' + '{:02X}'.format(self.__bytes[3])
                + ' ' + '{:02X}'.format(self.__bytes[4])
                + '|' + '{:02X}'.format(self.__bytes[5])
                + ' ' + '{:02X}'.format(self.__bytes[6])
                + '|' + '{:02X}'.format(self.__bytes[7])
                + ' ' + '{:02X}'.format(self.__bytes[8])
                + ' ' + '{:02X}'.format(self.__bytes[9])
                + ' ' + '{:02X}'.format(self.__bytes[10])
                + '] length: ' + str(self.__bytes[0])
                )
        return self._cache_str

    def __repr__(self):
        if self.__cache_repr is None:
            self.__cache_repr = str(self.__bytes)
        return self.__cache_repr

    def to_bytes(self):
        return self.__bytes

    @property
    def device_id(self):
        pass

    @device_id.getter
    def device_id(self):
        """Device-ID getter

        Returns:
            int: Device-ID
        """
        bs = self.__bytes[1:3]
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
        return self.__bytes[3] & 0x7F

    @property
    def func(self):
        pass

    @func.getter
    def func(self):
        """Function-Number getter.

        Returns:
            int: Function-Number
        """
        return self.__bytes[4]

    @property
    def rbit(self):
        pass

    @rbit.getter
    def rbit(self):
        """R-Bit getter

        Returns:
            bool: True if has R-Bit
        """
        return (self.__bytes[1] & 0x80) == 0x80

    @property
    def wbit(self):
        pass

    @wbit.getter
    def wbit(self):
        """W-Bit getter

        Returns:
            bool: True if has W-Bit
        """
        return (self.__bytes[3] & 0x80) == 0x80

    @property
    def ebit(self):
        pass

    @ebit.getter
    def ebit(self):
        """E-Bit getter.

        Returns:
            bool: True if has E-Bit
        """
        return (self.__bytes[5] & 0x80) == 0x80

    def get_block_number(self):
        bs = self.__bytes[5:7]
        return ((bs[0] << 8) & 0x7F00) | bs[1]

    def get_system_bytes(self):
        return self.__bytes[7:11]

    def is_next_block(self, block):
        bs = block.to_bytes()
        return (
            bs[1] == self.__bytes[1]
            and bs[2] == self.__bytes[2]
            and bs[3] == self.__bytes[3]
            and bs[4] == self.__bytes[4]
            and bs[7] == self.__bytes[7]
            and bs[8] == self.__bytes[8]
            and bs[9] == self.__bytes[9]
            and bs[10] == self.__bytes[10]
            and block.get_block_number() == (self.get_block_number() + 1)
        )

    def is_same_block(self, block):
        bs = block.to_bytes()
        return (
            bs[1] == self.__bytes[1]
            and bs[2] == self.__bytes[2]
            and bs[3] == self.__bytes[3]
            and bs[4] == self.__bytes[4]
            and bs[5] == self.__bytes[5]
            and bs[6] == self.__bytes[6]
            and bs[7] == self.__bytes[7]
            and bs[8] == self.__bytes[8]
            and bs[9] == self.__bytes[9]
            and bs[10] == self.__bytes[10]
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
                + self._ref_msg.get_header10bytes_str()
                + ')')

    def __repr__(self):
        return (self.__class__.__name__ + '('
                + repr(self._msg) + ','
                + repr(self._ref_msg.header10bytes)
                + ')')


class SecsSendMessageError(SecsWithReferenceMessageError):

    def __init__(self, msg, ref_msg):
        super(SecsSendMessageError, self).__init__(msg, ref_msg)


class SecsWaitReplyMessageError(SecsWithReferenceMessageError):

    def __init__(self, msg, ref_msg):
        super(SecsWaitReplyMessageError, self).__init__(msg, ref_msg)


class AbstractQueuing:

    def __init__(self):
        self.__terminated = False
        self._vv = list()
        self._v_cdt = threading.Condition()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.shutdown()

    def shutdown(self):
        with self._v_cdt:
            self.__terminated = True
            self._v_cdt.notify_all()

    def _is_terminated(self):
        with self._v_cdt:
            return self.__terminated

    def await_termination(self, timeout=None):
        with self._v_cdt:
            return self._v_cdt.wait_for(self._is_terminated, timeout)

    def put(self, value):
        with self._v_cdt:
            if value is not None and not self._is_terminated():
                self._vv.append(value)
                self._v_cdt.notify_all()

    def puts(self, values):
        with self._v_cdt:
            if values and not self._is_terminated():
                self._vv.extend([v for v in values])
                self._v_cdt.notify_all()

    def _poll_vv(self):
        with self._v_cdt:
            if self._vv:
                return self._vv.pop(0)
            else:
                return None


class CallbackQueuing(AbstractQueuing):

    def __init__(self, callback):
        super(CallbackQueuing, self).__init__()
        self._cb = callback

        def _f():
            with self._v_cdt:
                while True:
                    v = self._poll_vv()
                    if v is None:
                        self._v_cdt.wait()

                        if self._is_terminated():
                            self._cb(None)
                            return

                    else:
                        self._cb(v)

        threading.Thread(target=_f, daemon=True).start()


class WaitingQueuing(AbstractQueuing):

    def __init__(self):
        super(WaitingQueuing, self).__init__()

    def poll(self, timeout=None):

        with self._v_cdt:

            if self._is_terminated():
                return None

            v = self._poll_vv()
            if v is not None:
                return v

            self._v_cdt.wait(timeout)

            if self._is_terminated():
                return None

            return self._poll_vv()

    def put_to_list(self, values, pos, size, timeout=None):

        def _f(vv, p, m):
            vv_size = len(self._vv)
            if vv_size > 0:
                r = m - p
                if vv_size > r:
                    vv.extend(self._vv[0:r])
                    del self._vv[0:r]
                    return r
                else:
                    vv.extend(self._vv)
                    self._vv.clear()
                    return vv_size
            else:
                return -1

        with self._v_cdt:

            if self._is_terminated():
                return -1

            rr = _f(values, pos, size)
            if rr > 0:
                return rr

            self._v_cdt.wait(timeout)

            if self._is_terminated():
                return -1

            return _f(values, pos, size)


class AbstractSecsCommunicator:

    __DEFAULT_TIMEOUT_T1 = 1.0
    __DEFAULT_TIMEOUT_T2 = 15.0
    __DEFAULT_TIMEOUT_T3 = 45.0
    __DEFAULT_TIMEOUT_T4 = 45.0
    __DEFAULT_TIMEOUT_T5 = 10.0
    __DEFAULT_TIMEOUT_T6 = 5.0
    __DEFAULT_TIMEOUT_T7 = 10.0
    __DEFAULT_TIMEOUT_T8 = 5.0

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
        self.__comm_cdt = threading.Condition()

        self.__recv_primary_msg_lstnrs = list()
        self.__communicate_lstnrs = list()
        self.__error_lstnrs = list()
        self.__recv_all_msg_lstnrs = list()
        self.__sended_msg_lstnrs = list()

        recv_pri_msg_lstnr = kwargs.get('recv_primary_msg', None)
        if recv_pri_msg_lstnr is not None:
            self.add_recv_primary_msg_listener(recv_pri_msg_lstnr)

        err_lstnr = kwargs.get('error', None)
        if err_lstnr is not None:
            self.add_error_listener(err_lstnr)

        comm_lstnr = kwargs.get('communicate', None)
        if comm_lstnr is not None:
            self.add_communicate_listener(comm_lstnr)

        self.__opened = False
        self.__closed = False
        self._open_close_rlock = threading.RLock()

    @property
    def gem(self):
        pass

    @gem.getter
    def gem(self):
        """GEM getter

        Returns:
            Gem: GEM-instance
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
    def _try_gt_zero(v):
        """test-set-timeout-tx

        Args:
            v (int or float): timeout-time-seconds.

        Raises:
            TypeError: raise if v is None.
            ValueError: raise if v is not greater than 0.0.

        Returns:
            float: tested value
        """
        if v is None:
            raise TypeError("Timeout-value require not None")
        if v > 0.0:
            return float(v)
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
            val (int or float): Timeout-T1 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t1 = self._try_gt_zero(val)

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
            val (int or float): Timeout-T2 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t2 = self._try_gt_zero(val)

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
            val (int or float): Timeout-T3 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t3 = self._try_gt_zero(val)

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
            val (int or float): Timeout-T4 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t4 = self._try_gt_zero(val)

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
            val (int or float): Timeout-T5 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t5 = self._try_gt_zero(val)

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
            val (int or float): Timeout-T6 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t6 = self._try_gt_zero(val)

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
            val (int or float): Timeout-T7 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t7 = self._try_gt_zero(val)

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
            val (int or float): Timeout-T8 value.

        Raises:
            TypeError: if value is None.
            ValueError: if value is not greater than 0.0.
        """
        self.__timeout_t8 = self._try_gt_zero(val)

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

    def open_and_wait_until_communicating(self, timeout=None):

        if not self.is_open:
            self._open()

        with self.__comm_cdt:

            def _p():
                return self.is_closed or self.is_communicating

            r = self.__comm_cdt.wait_for(_p, timeout)
            if r:
                if self.is_closed:
                    raise SecsCommunicatorError("Communicator closed")
            return r

    @property
    def is_open(self):
        pass

    @is_open.getter
    def is_open(self):
        with self._open_close_rlock:
            return self.__opened and not self.__closed

    @property
    def is_closed(self):
        pass

    @is_closed.getter
    def is_closed(self):
        with self._open_close_rlock:
            return self.__closed

    def _set_opened(self):
        with self._open_close_rlock:
            self.__opened = True

    def _set_closed(self):
        with self._open_close_rlock:
            self.__closed = True
            with self.__comm_cdt:
                self.__comm_cdt.notify_all()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._close()

    def __del__(self):
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
            secs2body (Secs2Body or tuple, list, optional): SECS-II-body. Defaults to None.

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
            primary.system_bytes,
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
            SecsMessage: Reply-Message if exist, otherwise None
        """
        raise NotImplementedError()

    def add_recv_primary_msg_listener(self, listener):
        """Add receive-primary-message listener

        Args:
            listener (function):

        Returns:
            None
        """
        self.__recv_primary_msg_lstnrs.append(listener)

    def remove_recv_primary_msg_listener(self, listener):
        self.__recv_primary_msg_lstnrs.remove(listener)

    def _put_recv_primary_msg(self, recv_msg):
        if recv_msg is not None:
            for ls in self.__recv_primary_msg_lstnrs:
                ls(recv_msg, self)

    def add_recv_all_msg_listener(self, listener):
        self.__recv_all_msg_lstnrs.append(listener)

    def remove_recv_all_msg_listener(self, listener):
        self.__recv_all_msg_lstnrs.remove(listener)

    def _put_recv_all_msg(self, recv_msg):
        if recv_msg is not None:
            for ls in self.__recv_all_msg_lstnrs:
                ls(recv_msg, self)

    def add_sended_msg_listener(self, listener):
        self.__sended_msg_lstnrs.append(listener)

    def remove_sended_msg_listener(self, listener):
        self.__sended_msg_lstnrs.remove(listener)

    def _put_sended_msg(self, sended_msg):
        if sended_msg is not None:
            for ls in self.__sended_msg_lstnrs:
                ls(sended_msg, self)

    def add_communicate_listener(self, listener):
        with self.__comm_cdt:
            self.__communicate_lstnrs.append(listener)
            listener(self.__communicating, self)

    def remove_communicate_listener(self, listener):
        with self.__comm_cdt:
            self.__communicate_lstnrs.remove(listener)

    def _put_communicated(self, communicating):
        with self.__comm_cdt:
            if communicating != self.__communicating:
                self.__communicating = communicating
                for ls in self.__communicate_lstnrs:
                    ls(self.__communicating, self)
                self.__comm_cdt.notify_all()

    @property
    def is_communicating(self):
        pass

    @is_communicating.getter
    def is_communicating(self):
        with self.__comm_cdt:
            return self.__communicating

    def add_error_listener(self, listener):
        self.__error_lstnrs.append(listener)

    def remove_error_listener(self, listener):
        self.__error_lstnrs.remove(listener)

    def _put_error(self, e):
        if e is not None:
            for ls in self.__error_lstnrs:
                ls(e, self)


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

        self.__bbqq = WaitingQueuing()

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

                msg = HsmsSsMessage.from_bytes(bytes(heads) + bytes(bodys))

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

        if ctrl_type == HsmsSsControlType.DATA:
            if msg.wbit:
                timeout_tx = self.__comm.timeout_t3

        elif (ctrl_type == HsmsSsControlType.SELECT_REQ
              or ctrl_type == HsmsSsControlType.LINKTEST_REQ):

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

                        if ctrl_type == HsmsSsControlType.DATA:

                            raise HsmsSsTimeoutT3Error("HsmsSs-Timeout-T3", msg)

                        else:
                            self.shutdown()
                            raise HsmsSsTimeoutT6Error("HsmsSs-Timeout-T6", msg)

                else:

                    if rsp.get_control_type() == HsmsSsControlType.REJECT_REQ:

                        raise HsmsSsRejectMessageError("HsmsSs-Reject-Message", msg)

                    else:
                        return rsp

            finally:
                self.__send_reply_pool.remove(pack)

        else:
            _send()
            return None


class AbstractHsmsSsCommunicator(AbstractSecsCommunicator):

    def __init__(self, session_id, is_equip, **kwargs):
        super(AbstractHsmsSsCommunicator, self).__init__(session_id, is_equip, **kwargs)

        self._hsmsss_connection = None
        self._hsmsss_connection_lock = threading.Lock()

        self._hsmsss_comm = HsmsSsCommunicateState.NOT_CONNECT
        self._hsmsss_comm_lock = threading.Lock()
        self._hsmsss_comm_lstnrs = list()

        self.__recv_all_msg_putter = CallbackQueuing(self._put_recv_all_msg)
        self.__sended_msg_putter = CallbackQueuing(self._put_sended_msg)
        self.__error_putter = CallbackQueuing(super()._put_error)

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
            HsmsSsDataMessage(strm, func, wbit, secs2body, system_bytes, device_id))

    def send_hsmsss_msg(self, msg):
        def _f():
            with self._hsmsss_connection_lock:
                if self._hsmsss_connection is None:
                    raise HsmsSsSendMessageError("HsmsSsCommunicator not connected", msg)
                else:
                    return self._hsmsss_connection

        return _f().send(msg)

    def build_select_req(self):
        return HsmsSsControlMessage.build_select_request(
            self._create_system_bytes())

    @staticmethod
    def build_select_rsp(primary, status):
        return HsmsSsControlMessage.build_select_response(
            primary,
            status)

    def build_linktest_req(self):
        return HsmsSsControlMessage.build_linktest_request(
            self._create_system_bytes())

    @staticmethod
    def build_linktest_rsp(primary):
        return HsmsSsControlMessage.build_linktest_response(primary)

    @staticmethod
    def build_reject_req(primary, reason):
        return HsmsSsControlMessage.build_reject_request(primary, reason)

    def build_separate_req(self):
        return HsmsSsControlMessage.build_separate_request(
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
        with self._hsmsss_comm_lock:
            self._hsmsss_comm_lstnrs.append(listener)
            listener(self._hsmsss_comm, self)

    def remove_hsmsss_communicate_listener(self, listener):
        with self._hsmsss_comm_lock:
            self._hsmsss_comm_lstnrs.remove(listener)

    def _put_hsmsss_comm_state(self, state, callback=None):
        with self._hsmsss_comm_lock:
            if state != self._hsmsss_comm:
                self._hsmsss_comm = state
                for ls in self._hsmsss_comm_lstnrs:
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


class HsmsSsActiveCommunicator(AbstractHsmsSsCommunicator):

    __PROTOCOL = 'HSMS-SS-ACTIVE'

    def __init__(self, ip_address, port, session_id, is_equip, **kwargs):
        super(HsmsSsActiveCommunicator, self).__init__(session_id, is_equip, **kwargs)

        self.__ipaddr = (ip_address, port)

        self.__circuit_cdt = threading.Condition()

        self.__cdts = list()
        self.__cdts.append(self.__circuit_cdt)

        self.__ths = list()

        self.__recv_primary_msg_putter = CallbackQueuing(self._put_recv_primary_msg)

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

                            if (ss == HsmsSsSelectStatus.SUCCESS
                                    or ss == HsmsSsSelectStatus.ACTIVED):

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
                self._put_error(HsmsSsCommunicatorError(e))
        except HsmsSsCommunicatorError as e:
            if not self.is_closed:
                self._put_error(e)
        except HsmsSsSendMessageError as e:
            if not self.is_closed:
                self._put_error(e)
        except HsmsSsWaitReplyMessageError as e:
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
                if ctrl_type == HsmsSsControlType.DATA:

                    if self.get_hsmsss_communicate_state() == HsmsSsCommunicateState.SELECTED:

                        self.__recv_primary_msg_putter.put(recv_msg)

                    else:
                        conn.send(
                            self.build_select_rsp(
                                recv_msg,
                                HsmsSsRejectReason.NOT_SELECTED))

                elif ctrl_type == HsmsSsControlType.LINKTEST_REQ:

                    conn.send(self.build_linktest_rsp(recv_msg))

                elif ctrl_type == HsmsSsControlType.SEPARATE_REQ:

                    with self.__circuit_cdt:
                        self.__circuit_cdt.notify_all()

                elif ctrl_type == HsmsSsControlType.SELECT_REQ:

                    conn.send(
                        self.build_reject_req(
                            recv_msg,
                            HsmsSsRejectReason.NOT_SUPPORT_TYPE_S))

                elif (ctrl_type == HsmsSsControlType.SELECT_RSP
                      or ctrl_type == HsmsSsControlType.LINKTEST_RSP):

                    conn.send(
                        self.build_reject_req(
                            recv_msg,
                            HsmsSsRejectReason.TRANSACTION_NOT_OPEN))

                elif ctrl_type == HsmsSsControlType.REJECT_REQ:

                    # Nothing
                    pass

                else:

                    if HsmsSsControlType.has_s_type(recv_msg.get_s_type()):

                        conn.send(
                            self.build_reject_req(
                                recv_msg,
                                HsmsSsRejectReason.NOT_SUPPORT_TYPE_P))

                    else:

                        conn.send(
                            self.build_reject_req(
                                recv_msg,
                                HsmsSsRejectReason.NOT_SUPPORT_TYPE_S))

            except HsmsSsSendMessageError as e:
                self._put_error(e)
            except HsmsSsWaitReplyMessageError as e:
                self._put_error(e)
            except HsmsSsCommunicatorError as e:
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


class HsmsSsPassiveCommunicator(AbstractHsmsSsCommunicator):

    __PROTOCOL = 'HSMS-SS-PASSIVE'
    __TIMEOUT_REBIND = 5.0

    def __init__(self, ip_address, port, session_id, is_equip, **kwargs):
        super(HsmsSsPassiveCommunicator, self).__init__(session_id, is_equip, **kwargs)

        self.__ipaddr = (ip_address, port)

        self.__cdts = list()
        self.__ths = list()

        self.__recv_primary_msg_putter = CallbackQueuing(self._put_recv_primary_msg)

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
        self.__timeout_rebind = self._try_gt_zero(val)

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

                    def _f_sock(s):
                        with s:
                            try:
                                self.__accept_socket(s)
                            except Exception as ea:
                                if not self.is_closed:
                                    self._put_error(ea)
                            finally:
                                try:
                                    s.shutdown(socket.SHUT_RDWR)
                                except Exception as eb:
                                    if self.is_closed:
                                        self._put_error(eb)

                    try:
                        while not self.is_closed:
                            sock = (server.accept())[0]

                            threading.Thread(
                                target=_f_sock,
                                args=(sock, ),
                                daemon=True
                                ).start()

                    except Exception as ee:
                        if not self.is_closed:
                            self._put_error(HsmsSsCommunicatorError(ee))

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

                    try:
                        server.shutdown(socket.SHUT_RDWR)
                    except Exception as es:
                        if not self.is_closed:
                            self._put_error(es)

        except Exception as e:
            if not self.is_closed:
                self._put_error(HsmsSsCommunicatorError(e))

        finally:
            self.__cdts.remove(cdt)

    def __accept_socket(self, sock):

        qq = WaitingQueuing()

        cdt = threading.Condition()

        try:
            self.__cdts.append(cdt)

            def _put_to_qq(recv_msg, c):
                qq.put((recv_msg, c))

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
                if ctrl_type == HsmsSsControlType.DATA:

                    conn.send(
                        self.build_select_rsp(
                            recv_msg,
                            HsmsSsRejectReason.NOT_SELECTED))

                elif ctrl_type == HsmsSsControlType.LINKTEST_REQ:

                    conn.send(self.build_linktest_rsp(recv_msg))

                elif ctrl_type == HsmsSsControlType.SEPARATE_REQ:

                    return False

                elif ctrl_type == HsmsSsControlType.SELECT_REQ:

                    r = self._set_hsmsss_connection(
                        conn,
                        self._put_hsmsss_comm_state_to_selected)

                    if r:

                        conn.send(
                            self.build_select_rsp(
                                recv_msg,
                                HsmsSsSelectStatus.SUCCESS))

                        return True

                    else:

                        conn.send(
                            self.build_select_rsp(
                                recv_msg,
                                HsmsSsSelectStatus.ALREADY_USED))

                elif (ctrl_type == HsmsSsControlType.SELECT_RSP
                      or ctrl_type == HsmsSsControlType.LINKTEST_RSP):

                    conn.send(
                        self.build_reject_req(
                            recv_msg,
                            HsmsSsRejectReason.TRANSACTION_NOT_OPEN))

                elif ctrl_type == HsmsSsControlType.REJECT_REQ:

                    # Nothing
                    pass

                else:

                    if HsmsSsControlType.has_s_type(recv_msg.get_s_type()):

                        conn.send(
                            self.build_reject_req(
                                recv_msg,
                                HsmsSsRejectReason.NOT_SUPPORT_TYPE_P))

                    else:

                        conn.send(
                            self.build_reject_req(
                                recv_msg,
                                HsmsSsRejectReason.NOT_SUPPORT_TYPE_S))

            except HsmsSsSendMessageError as e:
                self._put_error(e)
            except HsmsSsWaitReplyMessageError as e:
                self._put_error(e)
            except HsmsSsCommunicatorError as e:
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
                if ctrl_type == HsmsSsControlType.DATA:

                    self.__recv_primary_msg_putter.put(recv_msg)

                elif ctrl_type == HsmsSsControlType.LINKTEST_REQ:

                    conn.send(self.build_linktest_rsp(recv_msg))

                elif ctrl_type == HsmsSsControlType.SEPARATE_REQ:

                    return False

                elif ctrl_type == HsmsSsControlType.SELECT_REQ:

                    conn.send(
                        self.build_select_rsp(
                            recv_msg,
                            HsmsSsSelectStatus.ACTIVED))

                elif (ctrl_type == HsmsSsControlType.SELECT_RSP
                      or ctrl_type == HsmsSsControlType.LINKTEST_RSP):

                    conn.send(
                        self.build_reject_req(
                            recv_msg,
                            HsmsSsRejectReason.TRANSACTION_NOT_OPEN))

                elif ctrl_type == HsmsSsControlType.REJECT_REQ:

                    # Nothing
                    pass

                else:

                    if HsmsSsControlType.has_s_type(recv_msg.get_s_type()):

                        conn.send(
                            self.build_reject_req(
                                recv_msg,
                                HsmsSsRejectReason.NOT_SUPPORT_TYPE_P))

                    else:

                        conn.send(
                            self.build_reject_req(
                                recv_msg,
                                HsmsSsRejectReason.NOT_SUPPORT_TYPE_S))

            except HsmsSsSendMessageError as e:
                self._put_error(e)
            except HsmsSsWaitReplyMessageError as e:
                self._put_error(e)
            except HsmsSsCommunicatorError as e:
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


class Secs1CommunicatorError(SecsCommunicatorError):

    def __init__(self, msg):
        super(Secs1CommunicatorError, self).__init__(msg)


class Secs1SendMessageError(SecsSendMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1SendMessageError, self).__init__(msg, ref_msg)


class Secs1RetryOverError(Secs1SendMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1RetryOverError, self).__init__(msg, ref_msg)


class Secs1WaitReplyMessageError(SecsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1WaitReplyMessageError, self).__init__(msg, ref_msg)


class Secs1TimeoutT3Error(Secs1WaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1TimeoutT3Error, self).__init__(msg, ref_msg)


class MsgAndRecvBytesWaitingQueuing(WaitingQueuing):

    def __init__(self):
        super(MsgAndRecvBytesWaitingQueuing, self).__init__()
        self.__msg_queue = list()

    def put_recv_bytes(self, bs):
        self.puts(bs)

    def entry_msg(self, msg):
        with self._v_cdt:
            if msg is not None and not self._is_terminated():
                self.__msg_queue.append(msg)
                self._v_cdt.notify_all()

    def poll_either(self, timeout=None):

        with self._v_cdt:

            if self._is_terminated():
                return None, None

            if self.__msg_queue:
                return self.__msg_queue.pop(0), None

            v = self._poll_vv()
            if v is not None:
                return None, v

            self._v_cdt.wait(timeout)

            if self._is_terminated():
                return None, None

            if self.__msg_queue:
                return self.__msg_queue.pop(0), None

            return None, self._poll_vv()

    def recv_bytes_garbage(self, timeout):

        with self._v_cdt:
            del self._vv[:]

            if self._is_terminated():
                return

            while True:
                v = self.poll(timeout)
                if v is None:
                    return


class SendSecs1MessagePack:

    def __init__(self, msg):
        self.__msg = msg
        self.__present = 0
        self.__lock = threading.Lock()
        self.__cdt = threading.Condition()
        self.__sended = False
        self.__except = None
        self.__timer_resetted = True
        self.__reply_msg = None

    def secs1msg(self):
        return self.__msg

    def present_block(self):
        return (self.__msg.to_blocks())[self.__present]

    def next_block(self):
        self.__present += 1

    def reset_block(self):
        self.__present = 0

    def ebit_block(self):
        return self.present_block().ebit

    def wait_until_sended(self, timeout=None):
        while True:
            with self.__lock:
                if self.__sended:
                    return
                elif self.__except is not None:
                    raise self.__except

            with self.__cdt:
                self.__cdt.wait(timeout)

    def notify_sended(self):
        with self.__lock:
            self.__sended = True
            with self.__cdt:
                self.__cdt.notify_all()

    def notify_except(self, e):
        with self.__lock:
            self.__except = e
            with self.__cdt:
                self.__cdt.notify_all()

    def wait_until_reply(self, timeout):

        with self.__lock:
            self.__timer_resetted = True

        while True:
            with self.__lock:
                if self.__reply_msg is not None:
                    return self.__reply_msg
                elif self.__timer_resetted:
                    self.__timer_resetted = False
                else:
                    return None

            with self.__cdt:
                self.__cdt.wait(timeout)

    def notify_reply_msg(self, msg):
        with self.__lock:
            self.__reply_msg = msg
            with self.__cdt:
                self.__cdt.notify_all()

    def notify_timer_reset(self):
        with self.__lock:
            self.__timer_resetted = True
            with self.__cdt:
                self.__cdt.notify_all()


class Secs1SendReplyPackPool:

    def __init__(self):
        self.__packs = list()
        self.__lock = threading.Lock()

    def append(self, pack):
        with self.__lock:
            self.__packs.append(pack)

    def remove(self, pack):
        with self.__lock:
            self.__packs.remove(pack)

    def __get_packs(self, system_bytes):
        with self.__lock:
            return [p for p in self.__packs
                    if p.secs1msg().system_bytes == system_bytes]

    def sended(self, msg):
        for p in self.__get_packs(msg.system_bytes):
            p.notify_sended()

    def raise_except(self, msg, e):
        for p in self.__get_packs(msg.system_bytes):
            p.notify_except(e)

    def receive(self, msg):
        pp = self.__get_packs(msg.system_bytes)
        if pp:
            for p in pp:
                p.notify_reply_msg(msg)
            return True
        else:
            return False

    def timer_reset(self, block):
        for p in self.__get_packs(block.get_system_bytes()):
            p.notify_timer_reset()


class AbstractSecs1Communicator(AbstractSecsCommunicator):

    __ENQ = 0x5
    __EOT = 0x4
    __ACK = 0x6
    __NAK = 0x15
    __BYTES_ENQ = bytes([__ENQ])
    __BYTES_EOT = bytes([__EOT])
    __BYTES_ACK = bytes([__ACK])
    __BYTES_NAK = bytes([__NAK])

    __DEFAULT_RETRY = 3

    def __init__(self, device_id, is_equip, is_master, **kwargs):
        super(AbstractSecs1Communicator, self).__init__(device_id, is_equip, **kwargs)
        self.is_master = is_master
        self.retry = kwargs.get('retry', self.__DEFAULT_RETRY)

        self.__msg_and_bytes_queue = MsgAndRecvBytesWaitingQueuing()
        self.__send_reply_pack_pool = Secs1SendReplyPackPool()
        self.__recv_blocks = list()

        self.__recv_primary_msg_putter = CallbackQueuing(self._put_recv_primary_msg)
        self.__recv_all_msg_putter = CallbackQueuing(self._put_recv_all_msg)
        self.__sended_msg_putter = CallbackQueuing(self._put_sended_msg)

        self.__error_putter = CallbackQueuing(super()._put_error)

        self.__recv_block_lstnrs = list()
        self.__recv_block_putter = CallbackQueuing(self._put_recv_block)

        self.__try_send_block_lstnrs = list()
        self.__try_send_block_putter = CallbackQueuing(self._put_try_send_block)

        self.__sended_block_lstnrs = list()
        self.__sended_block_putter = CallbackQueuing(self._put_sended_block)

        self.__secs1_circuit_error_msg_lstnrs = list()
        self.__secs1_circuit_error_msg_putter = CallbackQueuing(self._put_secs1_circuit_error_msg)

        self.__circuit_th = None

    @property
    def is_master(self):
        pass

    @is_master.getter
    def is_master(self):
        return self.__is_master

    @is_master.setter
    def is_master(self, val):
        self.__is_master = bool(val)

    @property
    def retry(self):
        pass

    @retry.getter
    def retry(self):
        return self.__retry

    @retry.setter
    def retry(self, val):
        if val is None:
            raise TypeError("retry-value require not None")
        else:
            v = int(val)
            if v >= 0:
                self.__retry = v
            else:
                raise ValueError("retry-value require >= 0")

    def _open(self):
        with self._open_close_rlock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")

            def _f():
                while self.__circuit():
                    pass

            self.__circuit_th = threading.Thread(target=_f, daemon=True)
            self.__circuit_th.start()

            self._set_opened()

    def _close(self):

        if self.is_closed:
            return

        self._set_closed()

        self.__recv_primary_msg_putter.shutdown()
        self.__recv_all_msg_putter.shutdown()
        self.__sended_msg_putter.shutdown()
        self.__error_putter.shutdown()
        self.__recv_block_putter.shutdown()
        self.__try_send_block_putter.shutdown()
        self.__sended_block_putter.shutdown()
        self.__secs1_circuit_error_msg_putter.shutdown()
        self.__msg_and_bytes_queue.shutdown()

        if self.__circuit_th is not None:
            self.__circuit_th.join(0.1)

    def _send(self, strm, func, wbit, secs2body, system_bytes, device_id):
        return self.send_secs1_msg(
            Secs1Message(strm, func, wbit, secs2body, system_bytes, device_id, self.is_equip))

    def send_secs1_msg(self, msg):

        pack = SendSecs1MessagePack(msg)

        try:
            self.__send_reply_pack_pool.append(pack)

            self.__msg_and_bytes_queue.entry_msg(pack)

            timeout_tx = self.timeout_t3 if msg.wbit else -1.0

            pack.wait_until_sended()

            self.__sended_msg_putter.put(pack.secs1msg())

            if timeout_tx > 0.0:

                r = pack.wait_until_reply(timeout_tx)
                if r is None:
                    raise Secs1TimeoutT3Error('Timeout-T3', pack.secs1msg())
                else:
                    return r
            else:
                return None

        finally:
            self.__send_reply_pack_pool.remove(pack)

    def _put_recv_bytes(self, bs):
        self.__msg_and_bytes_queue.put_recv_bytes(bs)

    def _send_bytes(self, bs):
        # prototype
        raise NotImplementedError()

    def _put_error(self, e):
        self.__error_putter.put(e)

    def add_recv_block_listener(self, listener):
        self.__recv_block_lstnrs.append(listener)

    def remove_recv_block_listener(self, listener):
        self.__recv_block_lstnrs.remove(listener)

    def _put_recv_block(self, block):
        if block is not None:
            for ls in self.__recv_block_lstnrs:
                ls(block, self)

    def add_try_send_block_listener(self, listener):
        self.__try_send_block_lstnrs.append(listener)

    def remove_try_send_block_listener(self, listener):
        self.__try_send_block_lstnrs.remove(listener)

    def _put_try_send_block(self, block):
        if block is not None:
            for ls in self.__try_send_block_lstnrs:
                ls(block, self)

    def add_sended_block_listener(self, listener):
        self.__sended_block_lstnrs.append(listener)

    def remove_sended_block_listener(self, listener):
        self.__sended_block_lstnrs.remove(listener)

    def _put_sended_block(self, block):
        if block is not None:
            for ls in self.__sended_block_lstnrs:
                ls(block, self)

    def add_secs1_circuit_error_msg_listener(self, listener):
        self.__secs1_circuit_error_msg_lstnrs.append(listener)

    def remove_secs1_circuit_error_msg_listener(self, listener):
        self.__secs1_circuit_error_msg_lstnrs.remove(listener)

    def _put_secs1_circuit_error_msg(self, msg_obj):
        if msg_obj is not None:
            for ls in self.__secs1_circuit_error_msg_lstnrs:
                ls(msg_obj, self)

    def __circuit(self):

        pack, b = self.__msg_and_bytes_queue.poll_either()

        if pack is not None:

            try:
                count = 0
                while count <= self.retry:

                    if self.is_closed:
                        return False

                    self._send_bytes(self.__BYTES_ENQ)

                    while True:

                        if self.is_closed:
                            return False

                        b = self.__msg_and_bytes_queue.poll(self.timeout_t2)

                        if b is None:

                            self.__secs1_circuit_error_msg_putter.put({
                                'msg': 'Timeout-T2-Wait-EOT'
                            })

                            count += 1

                            self.__secs1_circuit_error_msg_putter.put({
                                'msg': 'Retry-Count-Up',
                                'count': count
                            })

                            break

                        elif b == self.__ENQ and not self.is_master:

                            try:
                                self.__circuit_receiving()

                            except Secs1CommunicatorError as e:
                                self._put_error(e)

                            count = 0
                            pack.reset_block()
                            break

                        elif b == self.__EOT:

                            if self.__circuit_sending(pack.present_block()):

                                if pack.ebit_block():

                                    pack.notify_sended()
                                    return True

                                else:

                                    pack.next_block()
                                    count = 0
                                    break

                            else:

                                count += 1

                                self.__secs1_circuit_error_msg_putter.put({
                                    'msg': 'Retry-Count-Up',
                                    'count': count
                                })

                pack.notify_except(Secs1RetryOverError(
                    "Send-Message Retry-Over",
                    pack.secs1msg()))

            except Secs1SendMessageError as e:
                if not self.is_closed:
                    pack.notify_except(e)

            except Secs1CommunicatorError as e:
                if not self.is_closed:
                    pack.notify_except(e)

            return True

        elif b is not None:

            if b == self.__ENQ:

                try:
                    self.__circuit_receiving()

                except Secs1CommunicatorError as e:
                    if not self.is_closed:
                        self._put_error(e)

            return True

        else:
            return False

    def __circuit_sending(self, block):

        self.__try_send_block_putter.put(block)

        self._send_bytes(block.to_bytes())

        b = self.__msg_and_bytes_queue.poll(self.timeout_t2)

        if b is None:

            self.__secs1_circuit_error_msg_putter.put({
                'msg': 'Timeout-T2-Wait-ACK',
                'block': block
            })

            return False

        elif b == self.__ACK:

            self.__sended_block_putter.put(block)
            return True

        else:

            self.__secs1_circuit_error_msg_putter.put({
                'msg': 'Receive-NOT-ACK',
                'block': block,
                'recv': b
            })

            return False

    def __circuit_receiving(self):

        try:
            self._send_bytes(self.__BYTES_EOT)

            bb = list()

            r = self.__msg_and_bytes_queue.put_to_list(
                bb, 0, 1,
                self.timeout_t2)

            if r <= 0:
                self._send_bytes(self.__BYTES_NAK)

                self.__secs1_circuit_error_msg_putter.put({
                    'msg': 'Timeout-T2-Length-Byte'
                })

                return

            bb_len = bb[0]
            if bb_len < 10 or bb_len > 254:
                self.__msg_and_bytes_queue.recv_bytes_garbage(self.timeout_t1)
                self._send_bytes(self.__BYTES_NAK)

                self.__secs1_circuit_error_msg_putter.put({
                    'msg': 'Length-Byte-Error',
                    'length': bb_len
                })

                return

            pos = 1
            m = bb_len + 3

            while pos < m:
                r = self.__msg_and_bytes_queue.put_to_list(
                    bb, pos, m,
                    self.timeout_t1)

                if r <= 0:
                    self._send_bytes(self.__BYTES_NAK)

                    self.__secs1_circuit_error_msg_putter.put({
                        'msg': 'Timeout-T1',
                        'pos': pos
                    })

                    return

                pos += r

            if self.__sum_check(bb):

                self._send_bytes(self.__BYTES_ACK)

            else:

                self.__msg_and_bytes_queue.recv_bytes_garbage(self.timeout_t1)
                self._send_bytes(self.__BYTES_NAK)

                self.__secs1_circuit_error_msg_putter.put({
                    'msg': 'Sum-Check-Error',
                    'bytes': bytes(bb)
                })

                return

            block = Secs1MessageBlock(bytes(bb))

            self.__recv_block_putter.put(block)

            if block.device_id != self.device_id:

                self.__secs1_circuit_error_msg_putter.put({
                    'msg': 'Unmatch DEVICE-ID',
                    'deviceId': block.device_id
                })

                return

            if self.__recv_blocks:

                prev_block = self.__recv_blocks[-1]

                if prev_block.is_next_block(block):

                    self.__recv_blocks.append(block)

                else:

                    if not prev_block.is_same_block(block):

                        del self.__recv_blocks[:]
                        self.__recv_blocks.append(block)

            else:
                self.__recv_blocks.append(block)

            if block.ebit:

                try:
                    msg = Secs1Message.from_blocks(self.__recv_blocks)

                    if not self.__send_reply_pack_pool.receive(msg):

                        self.__recv_primary_msg_putter.put(msg)

                    self.__recv_all_msg_putter.put(msg)

                except Secs1MessageParseError as e:
                    self._put_error(e)

                finally:
                    del self.__recv_blocks[:]

            else:

                self.__send_reply_pack_pool.timer_reset(block)

                b = self.__msg_and_bytes_queue.poll(self.timeout_t4)

                if b is None:

                    self.__secs1_circuit_error_msg_putter.put({
                        'msg': 'Timeout-T4',
                        'prevBlock': block
                    })

                elif b == self.__ENQ:

                    self.__circuit_receiving()

                else:

                    self.__secs1_circuit_error_msg_putter.put({
                        'msg': 'Receive-NOT-ENQ-of-Next-Block',
                        'prevBlock': block
                    })

        except Secs1CommunicatorError as e:
            self._put_error(e)

    @staticmethod
    def __sum_check(bb):
        a = sum(bb[1:-2]) & 0xFFFF
        b = (bb[-2] << 8) | bb[-1]
        return a == b


class AbstractSecs1OnTcpIpCommunicator(AbstractSecs1Communicator):

    def __init__(self, device_id, is_equip, is_master, **kwargs):
        super(AbstractSecs1OnTcpIpCommunicator, self).__init__(device_id, is_equip, is_master, **kwargs)

        self.__sockets = list()
        self.__lock_sockets = threading.Lock()

    def _add_socket(self, sock):
        with self.__lock_sockets:
            self.__sockets.append(sock)
            self._put_communicated(bool(self.__sockets))

    def _remove_socket(self, sock):
        with self.__lock_sockets:
            self.__sockets.remove(sock)
            self._put_communicated(bool(self.__sockets))

    def _send_bytes(self, bs):

        with self.__lock_sockets:
            if self.__sockets:
                try:
                    for sock in self.__sockets:
                        sock.sendall(bs)

                except Exception as e:
                    raise Secs1CommunicatorError(e)

            else:
                raise Secs1CommunicatorError("Not connected")

    def _reading(self, sock):
        try:
            while not self.is_closed:
                bs = sock.recv(4096)
                if bs:
                    self._put_recv_bytes(bs)
                else:
                    return

        except Exception as e:
            if not self.is_closed:
                self._put_error(e)


class Secs1OnTcpIpCommunicator(AbstractSecs1OnTcpIpCommunicator):

    __DEFAULT_RECONNECT = 5.0
    __PROTOCOL = 'SECS-I-on-TCP/IP'

    def __init__(self, ip_address, port, device_id, is_equip, is_master, **kwargs):
        super(Secs1OnTcpIpCommunicator, self).__init__(device_id, is_equip, is_master, **kwargs)

        self.__ipaddr = (ip_address, port)

        self.__ths = list()
        self.__cdts = list()

        self.reconnect = kwargs.get('reconnect', self.__DEFAULT_RECONNECT)

    def __str__(self):
        return str({
            'protocol': self.__PROTOCOL,
            'ip_address': (self.__ipaddr[0] + ':' + str(self.__ipaddr[1])),
            'device_id': self.device_id,
            'is_equip': self.is_equip,
            'is_master': self.is_master,
            'name': self.name
        })

    def __repr__(self):
        return repr({
            'protocol': self.__PROTOCOL,
            'ip_address': self.__ipaddr,
            'device_id': self.device_id,
            'is_equip': self.is_equip,
            'is_master': self.is_master,
            'name': self.name
        })

    @property
    def reconnect(self):
        pass

    @reconnect.getter
    def reconnect(self):
        return self.__reconnect

    @reconnect.setter
    def reconnect(self, val):
        self.__reconnect = self._try_gt_zero(val)

    def _open(self):
        with self._open_close_rlock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")

            def _connecting():

                cdt = threading.Condition()

                try:
                    self.__cdts.append(cdt)

                    while not self.is_closed:

                        try:
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

                                try:
                                    sock.connect(self.__ipaddr)

                                    def _f():
                                        self._reading(sock)
                                        with cdt:
                                            cdt.notify_all()

                                    th_r = threading.Thread(target=_f, daemon=True)
                                    th_r.start()

                                    try:
                                        self.__ths.append(th_r)
                                        self._add_socket(sock)

                                        with cdt:
                                            cdt.wait()
                                    finally:
                                        self.__ths.remove(th_r)
                                        self._remove_socket(sock)

                                finally:
                                    try:
                                        sock.shutdown(socket.SHUT_RDWR)
                                    except Exception as e:
                                        if not self.is_closed:
                                            self._put_error(e)

                        except Exception as e:
                            if not self.is_closed:
                                self._put_error(e)

                        if self.is_closed:
                            return

                        with cdt:
                            cdt.wait(timeout=self.reconnect)

                finally:
                    self.__cdts.remove(cdt)

            th = threading.Thread(target=_connecting, daemon=True)
            th.start()
            self.__ths.append(th)

            super()._open()

            self._set_opened()

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


class Secs1OnTcpIpReceiverCommunicator(AbstractSecs1OnTcpIpCommunicator):

    __DEFAULT_REBIND = 5.0
    __PROTOCOL = 'SECS-I-on-TCP/IP-Receiver'

    def __init__(self, ip_address, port, device_id, is_equip, is_master, **kwargs):
        super(Secs1OnTcpIpReceiverCommunicator, self).__init__(device_id, is_equip, is_master, **kwargs)

        self.__ipaddr = (ip_address, port)

        self.__ths = list()
        self.__cdts = list()

        self.rebind = kwargs.get('rebind', self.__DEFAULT_REBIND)

    def __str__(self):
        return str({
            'protocol': self.__PROTOCOL,
            'ip_address': (self.__ipaddr[0] + ':' + str(self.__ipaddr[1])),
            'device_id': self.device_id,
            'is_equip': self.is_equip,
            'is_master': self.is_master,
            'name': self.name
        })

    def __repr__(self):
        return repr({
            'protocol': self.__PROTOCOL,
            'ip_address': self.__ipaddr,
            'device_id': self.device_id,
            'is_equip': self.is_equip,
            'is_master': self.is_master,
            'name': self.name
        })

    @property
    def rebind(self):
        pass

    @rebind.getter
    def rebind(self):
        return self.__rebind

    @rebind.setter
    def rebind(self, val):
        self.__rebind = self._try_gt_zero(val)

    def _open(self):
        with self._open_close_rlock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")

            def _open_server():

                cdt = threading.Condition()

                try:
                    self.__cdts.append(cdt)

                    while not self.is_closed:

                        try:
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

                                try:
                                    server.bind(self.__ipaddr)
                                    server.listen()

                                    while not self.is_closed:

                                        sock = (server.accept())[0]

                                        th_a = threading.Thread(target=self.__accept, args=(sock,), daemon=True)
                                        th_a.start()
                                        self.__ths.append(th_a)

                                finally:
                                    try:
                                        server.shutdown(socket.SHUT_RDWR)
                                    except Exception as ee:
                                        if not self.is_closed:
                                            self._put_error(ee)

                        except Exception as e:
                            if not self.is_closed:
                                self._put_error(e)

                        if self.is_closed:
                            return

                        with cdt:
                            cdt.wait(timeout=self.rebind)

                finally:
                    self.__cdts.remove(cdt)

            th = threading.Thread(target=_open_server, daemon=True)
            th.start()
            self.__ths.append(th)

            super()._open()

            self._set_opened()

    def __accept(self, sock):

        with sock:

            cdt = threading.Condition()

            try:
                self.__cdts.append(cdt)

                def _f():
                    self._reading(sock)
                    with cdt:
                        cdt.notify_all()

                th_r = threading.Thread(target=_f, daemon=True)
                th_r.start()

                try:
                    self.__ths.append(th_r)
                    self._add_socket(sock)

                    with cdt:
                        cdt.wait()

                finally:
                    self._remove_socket(sock)
                    self.__ths.remove(th_r)

            finally:
                self.__cdts.remove(cdt)

                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except Exception as e:
                    if not self.is_closed:
                        self._put_error(e)

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


class Secs1OnPySerialCommunicator(AbstractSecs1Communicator):

    __DEFAULT_REOPEN = 5.0
    __PROTOCOL = 'SECS-I-on-pySerial'

    def __init__(self, port, baudrate, device_id, is_equip, is_master, **kwargs):
        super(Secs1OnPySerialCommunicator, self).__init__(device_id, is_equip, is_master, **kwargs)

        self.__port = port
        self.__baudrate = baudrate

        self.__ths = list()
        self.__cdts = list()

        self.reopen = kwargs.get('reopen', self.__DEFAULT_REOPEN)

        self.__serial = None
        self.__serial_lock = threading.Lock()

    def __str__(self):
        return str({
            'protocol': self.__PROTOCOL,
            'port': self.__port,
            'baudrate': self.__baudrate,
            'device_id': self.device_id,
            'is_equip': self.is_equip,
            'is_master': self.is_master,
            'name': self.name
        })

    def __repr__(self):
        return repr({
            'protocol': self.__PROTOCOL,
            'port': self.__port,
            'baudrate': self.__baudrate,
            'device_id': self.device_id,
            'is_equip': self.is_equip,
            'is_master': self.is_master,
            'name': self.name
        })

    @property
    def reopen(self):
        pass

    @reopen.getter
    def reopen(self):
        return self.__reopen

    @reopen.setter
    def reopen(self, val):
        self.__reopen = self._try_gt_zero(val)

    def __set_serial(self, ser):
        with self.__serial_lock:
            self.__serial = ser
            self._put_communicated(self.__serial is not None)

    def __unset_serial(self):
        with self.__serial_lock:
            self.__serial_lock = None
            self._put_communicated(self.__serial is not None)

    def _send_bytes(self, bs):
        with self.__serial_lock:
            if self.__serial is None:
                raise Secs1CommunicatorError("Not connected")
            else:
                try:
                    self.__serial.write(bs)
                except Exception as e:
                    raise Secs1CommunicatorError(e)

    def _reading(self, ser):
        try:
            while not self.is_closed:
                bs = ser.read()
                if bs:
                    self._put_recv_bytes(bs)
                else:
                    return
        except Exception as e:
            self._put_error(e)

    def _open(self):
        with self._open_close_rlock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")

            try:
                serial = importlib.import_module('serial')
            except ModuleNotFoundError as ex:
                print("Secs1OnPySerialCommunicator require 'pySerial'")
                raise ex

            def _f():
                cdt = threading.Condition()

                try:
                    self.__cdts.append(cdt)

                    while not self.is_closed:

                        try:
                            ser = serial.Serial(
                                baudrate=self.__baudrate,
                                bytesize=serial.EIGHTBITS,
                                parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE
                            )

                            try:
                                ser.port = self.__port
                                ser.open()

                                def _ff():
                                    self._reading(ser)
                                    with cdt:
                                        cdt.notify_all()

                                th_r = threading.Thread(target=_ff, daemon=True)
                                th_r.start()

                                try:
                                    self.__ths.append(th_r)
                                    self.__set_serial(ser)

                                    with cdt:
                                        cdt.wait()

                                finally:
                                    self.__unset_serial()
                                    self.__ths.remove(th_r)

                            finally:
                                try:
                                    ser.close()
                                except Exception as ee:
                                    if not self.is_closed:
                                        self._put_error(ee)

                        except Exception as e:
                            if not self.is_closed:
                                self._put_error(e)

                        if self.is_closed:
                            return

                        with cdt:
                            cdt.wait(timeout=self.reopen)

                finally:
                    self.__cdts.remove(cdt)

            th = threading.Thread(target=_f, daemon=True)
            th.start()
            self.__ths.append(th)

            super()._open()

            self._set_opened()

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


class ClockType:
    A12 = 'A12'
    A16 = 'A16'


class Clock:

    def __init__(self, dt):
        self._datetime = dt

    def to_a16(self):
        return Secs2BodyBuilder.build('A', (
            self._datetime.strftime('%Y%m%d%H%M%S')
            + '{:02}'.format(int(self._datetime.microsecond/10000))
        ))

    def to_a12(self):
        return Secs2BodyBuilder.build('A', (
            self._datetime.strftime('%y%m%d%H%M%S')
        ))

    def to_datetime(self):
        return self._datetime

    @classmethod
    def now(cls):
        return Clock(datetime.datetime.now())

    @classmethod
    def from_ascii(cls, v):

        if v is not None:

            if v.type == 'A':

                m = len(v.value)

                if m == 12:

                    return Clock(datetime.datetime(
                        cls.__get_year(int(v.value[0:2])),
                        int(v.value[2:4]),
                        int(v.value[4:6]),
                        int(v.value[6:8]),
                        int(v.value[8:10]),
                        int(v.value[10:12])
                    ))

                elif m == 16:

                    return Clock(datetime.datetime(
                        int(v.value[0:4]),
                        int(v.value[4:6]),
                        int(v.value[6:8]),
                        int(v.value[8:10]),
                        int(v.value[10:12]),
                        int(v.value[12:14]),
                        (int(v.value[14:16]) * 10000)
                    ))

        raise Secs2BodyParseError("Unknown ClockType")

    @classmethod
    def __get_year(cls, yy):

        now_year = datetime.datetime.now().year
        century = int(now_year / 100) * 100
        flac_year = now_year % 100

        if flac_year < 25:

            if yy >= 75:
                return century - 100 + yy

        elif flac_year >= 75:

            if yy < 25:
                return century + 100 + yy

        return century + yy


class COMMACK:
    OK = 0x0
    DENIED = 0x1


class OFLACK:
    OK = 0x0


class ONLACK:
    OK = 0x0
    REFUSE = 0x1
    ALREADY_ONLINE = 0x2


class TIACK:
    OK = 0x0
    NOT_DONE = 0x1


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

            s2b = self._comm.send(
                1, 13, True,
                ('L', [
                    ('A', self.mdln),
                    ('A', self.softrev)
                ])
            ).secs2body

        else:

            s2b = self._comm.send(
                1, 13, True,
                ('L', [])
            ).secs2body

        if s2b is not None:
            if s2b.type == 'L':
                if s2b[0].type == 'B':
                    return s2b[0][0]

        raise Secs2BodyParseError("S1F14 not COMMACK")

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

        s2b = self._comm.send(1, 15, True).secs2body

        if s2b is not None:
            if s2b.type == 'B':
                return s2b[0]

        raise Secs2BodyParseError("S1F16 not OFLACK")

    def s1f16(self, primary_msg):
        return self._comm.reply(
            primary_msg,
            1, 16, False,
            ('B', [OFLACK.OK])
        )

    def s1f17(self):

        s2b = self._comm.send(1, 17, True).secs2body

        if s2b is not None:
            if s2b.type == 'B':
                return s2b[0]

        raise Secs2BodyParseError("S1F18 not ONLACK")

    def s1f18(self, primary_msg, onlack):
        return self._comm.reply(
            primary_msg,
            1, 18, False,
            ('B', [onlack])
        )

    def s2f17(self):

        s2b = self._comm.send(2, 17, True).secs2body

        try:
            return Clock.from_ascii(s2b)
        except Secs2BodyParseError:
            raise Secs2BodyParseError("S2F18 not time")

    def s2f18_now(self, primary_msg):
        return self.s2f18(primary_msg, Clock.now())

    def s2f18(self, primary_msg, clock):

        if self.clock_type == ClockType.A12:
            s2b = clock.to_a12()
        else:
            s2b = clock.to_a16()

        return self._comm.reply(primary_msg, 2, 18, False, s2b)

    def s2f31_now(self):
        return self.s2f31(Clock.now())

    def s2f31(self, clock):

        if self.clock_type == ClockType.A12:
            ss = clock.to_a12()
        else:
            ss = clock.to_a16()

        rr = self._comm.send(2, 31, True, ss).secs2body

        if rr is not None:
            if rr.type == 'B':
                return rr[0]

        raise Secs2BodyParseError("S2F32 not TIACK")

    def s2f32(self, primary_msg, tiack):
        return self._comm.reply(
            primary_msg,
            2, 32, False,
            ('B', [tiack])
        )

    def __s9fy(self, ref_msg, func):
        return self._comm.send(
            9, func, False,
            ('B', ref_msg.header10bytes)
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
