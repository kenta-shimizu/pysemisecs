import secs


class Secs1MessageParseError(secs.SecsMessageParseError):

    def __init__(self, msg):
        super(Secs1MessageParseError, self).__init__(msg)


class Secs1Message(secs.SecsMessage):

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
                secs.Secs2BodyBuilder.from_body_bytes(bs) if bs else None,
                blocks[0].get_system_bytes(),
                blocks[0].device_id,
                blocks[0].rbit
            )
            v.__cache_blocks = tuple(blocks)
            return v

        except secs.Secs2BodyParseError as e:
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
