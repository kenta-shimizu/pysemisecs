import os
import struct


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
