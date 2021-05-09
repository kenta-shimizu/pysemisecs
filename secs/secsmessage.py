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

        self._strm = strm
        self._func = func
        self._wbit = wbit
        self._secs2body = secs2body
        self._cache_header10bytes_str = None

    def get_stream(self):
        """
        Stream-Number getter.
        """
        return self._strm

    def get_function(self):
        """
        Function-Number getter.
        """
        return self._func

    def has_wbit(self):
        """
        Returns True if has W-Bit.
        """
        return self._wbit
    
    def get_secs2body(self):
        return self._secs2body

    def get_system_bytes(self):
        return (self._header10bytes())[6:10]

    def _header10bytes(self):
        return bytes(10)
        
    def _header10bytes_str(self):

        if self._cache_header10bytes_str is None:

            x = self._header10bytes()
            self._cache_header10bytes_str = (
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

        return self._cache_header10bytes_str
