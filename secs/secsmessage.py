import os


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
        """Stream-Number getter.

        Returns:
            int: Stream-Number
        """
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
        """Function-Number getter.

        Returns:
            int: Function-Number
        """
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
        """W-Bit getter

        Returns:
            bool: True if has W-Bit
        """
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
        """Secs2Body getter.

        Returns:
            secs.AbstractSecs2Body: Secs2Body
        """
        return self.__secs2body

    def get_secs2body(self):
        """Secs2Body getter.

        Alias of self.secs2body

        Returns:
            secs.AbstractSecs2Body: Secs2Body
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
        """ system-4-bytes getter.

        Returns:
            bytes: system-4-bytes, header10bytes[6:10]
        """
        return (self._header10bytes())[6:10]

    @property
    def header10bytes(self):
        pass

    @header10bytes.getter
    def header10bytes(self):
        """ header-10-bytes getter.

        Returns:
            bytes: header-10-bytes
        """
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
