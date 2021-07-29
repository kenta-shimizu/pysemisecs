import datetime
import secs


class ClockType:
    A12 = 'A12'
    A16 = 'A16'


class Clock:

    def __init__(self, dt):
        self._datetime = dt

    def to_a16(self):
        return secs.Secs2BodyBuilder.build('A', (
            self._datetime.strftime('%Y%m%d%H%M%S')
            + '{:02}'.format(int(self._datetime.microsecond/10000))
        ))

    def to_a12(self):
        return secs.Secs2BodyBuilder.build('A', (
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

        raise secs.Secs2BodyParseError("Unknown ClockType")
    
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
        
        raise secs.Secs2BodyParseError("S1F14 not COMMACK")

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
        
        raise secs.Secs2BodyParseError("S1F16 not OFLACK")

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
        
        raise secs.Secs2BodyParseError("S1F18 not ONLACK")

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
        except secs.Secs2BodyParseError as e:
            raise secs.Secs2BodyParseError("S2F18 not time")

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

        raise secs.Secs2BodyParseError("S2F32 not TIACK")

    def s2f32(self, primary_msg, tiack):
        return self._comm.reply(
            primary_msg,
            2, 32, False,
            ('B', [tiack])
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
