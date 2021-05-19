import secs


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
