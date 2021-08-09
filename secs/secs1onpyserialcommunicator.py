import threading
import importlib
import secs

class Secs1OnPySerialCommunicator(secs.AbstractSecs1Communicator):

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
        self.__reopen = float(val)

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
                raise secs.Secs1CommunicatorError("Not connected")
            else:
                try:
                    self.__serial.write(bs)
                except Exception as e:
                    raise secs.Secs1CommunicatorError(e)

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
            except ModuleNotFoundError as e:
                print("Secs1OnPySerialCommunicator require 'pySerial'")
                raise e

            def _f():
                cdt = threading.Condition()

                try:
                    self.__cdts.append(cdt)

                    while not self.is_closed:

                        try:
                            ser = serial.Serial(
                                port=self.__port,
                                baudrate=self.__baudrate,
                                bytesize=serial.EIGHTBITS,
                                parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE
                            )

                            try:
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
                                except Exception as e:
                                    if not self.is_closed:
                                        self._put_error(e)

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
