from threading import settrace
import secs

class ClockType:
    A12 = 'A12'
    A16 = 'A16'

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
    
    def __s9fy(self, ref_msg, func):
        self._comm.send(
            9, func, False,
            ('B', ref_msg._header10bytes())
            )

    def s9f1(self, ref_msg):
        self.__s9fy(ref_msg, 1)

    def s9f3(self, ref_msg):
        self.__s9fy(ref_msg, 3)

    def s9f5(self, ref_msg):
        self.__s9fy(ref_msg, 5)

    def s9f7(self, ref_msg):
        self.__s9fy(ref_msg, 7)

    def s9f9(self, ref_msg):
        self.__s9fy(ref_msg, 9)

    def s9f11(self, ref_msg):
        self.__s9fy(ref_msg, 11)
