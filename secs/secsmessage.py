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
