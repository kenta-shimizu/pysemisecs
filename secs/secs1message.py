import secs


class Secs1MessageParseError(secs.SecsMessageParseError):

    def __init__(self, msg):
        super(Secs1MessageParseError, self).__init__(msg)


class Secs1Message(secs.SecsMessage):

    def __init__(self, strm, func, wbit, secs2body, system_bytes, device_id, rbit):
        super(Secs1Message, self).__init__(strm, func, wbit, secs2body)
        self._system_bytes = system_bytes
        self._device_id = device_id
        self._rbit = rbit
        self._cache_header10bytes = None
        self._cache_str = None
        self._cache_repr = None
        self._cache_blocks = None

    def __str__(self):
        if self._cache_str is None:
            vv = [
                self._header10bytes_str(),
                self._STR_LINESEPARATOR,
                'S', str(self._strm),
                'F', str(self._func)
            ]
            if self._wbit:
                vv.append(' W')
            if self._secs2body is not None:
                vv.append(self._STR_LINESEPARATOR)
                vv.append(self._secs2body.to_sml())
            vv.append('.')
            self._cache_str = ''.join(vv)
        return self._cache_str

    def __repr__(self):
        if self._cache_repr is None:
            vv = [
                "{'header':", str(self._header10bytes()),
                ",'strm':", str(self._strm),
                ",'func':", str(self._func),
                ",'wbit':", str(self._wbit)
            ]
            if self._secs2body is not None:
                vv.append(",'secs2body':")
                vv.append(repr(self._secs2body))
            vv.append("}")
            self._cache_repr = ''.join(vv)
        return self._cache_repr

    def _header10bytes(self):
        if self._cache_header10bytes is None:
            b0 = (self._device_id >> 8) & 0x7F
            if self._rbit:
                b0 |= 0x80
            b1 = self._device_id & 0xFF
            b2 = self._strm & 0x7F
            if self._wbit:
                b2 |= 0x80
            b3 = self._func & 0xFF
            self._cache_header10bytes = bytes([
                b0, b1,
                b2, b3,
                0x00, 0x00,
                self._system_bytes[0], self._system_bytes[1],
                self._system_bytes[2], self._system_bytes[3]
            ])
        return self._cache_header10bytes

    def device_id(self):
        return self._device_id

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
        
        if self._cache_blocks is None:

            h10bs = self._header10bytes()
            if self._secs2body is None:
                bodybs = bytes()
            else:
                bodybs = self._secs2body.to_bytes()

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

            self._cache_blocks = tuple(blocks)

        return self._cache_blocks

    @classmethod
    def from_blocks(cls, blocks):

        if blocks is None or len(blocks) == 0:
            raise Secs1MessageParseError("No blocks")

        bs = b''.join([(x.to_bytes())[11:-2] for x in blocks])

        v = Secs1Message(
            blocks[0].get_stream(),
            blocks[0].get_function(),
            blocks[0].has_wbit(),
            secs.Secs2BodyBuilder.from_body_bytes(bs) if len(bs) > 0 else None,
            blocks[0].get_system_bytes(),
            blocks[0].device_id(),
            blocks[0].has_rbit()
        )
        v._cache_blocks = blocks
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

    def device_id(self):
        bs = self._bytes[1:3]
        return ((bs[0] << 8) & 0x7F00) | bs[1]

    def get_stream(self):
        return self._bytes[3] & 0x7F

    def get_function(self):
        return self._bytes[4]

    def has_rbit(self):
        return (self._bytes[1] & 0x80) == 0x80

    def has_wbit(self):
        return (self._bytes[3] & 0x80) == 0x80

    def has_ebit(self):
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
