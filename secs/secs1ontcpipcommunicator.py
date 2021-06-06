import threading
import concurrent
import socket
import secs


class AbstractSecs1OnTcpIpCommunicator(secs.AbstractSecs1Communicator):

    def __init__(self, session_id, is_equip, is_master, **kwargs):
        super(AbstractSecs1OnTcpIpCommunicator, self).__init__(session_id, is_equip, is_master, **kwargs)

        self.__sockets = list()
        self.__lock_sockets = threading.Lock()

    def _add_socket(self, sock):
        with self.__lock_sockets:
            self.__sockets.append(sock)
            self._put_communicated(bool(self.__sockets))

    def _remove_socket(self, sock):
        with self.__lock_sockets:
            self.__sockets.remove(sock)
            self._put_communicated(bool(self.__sockets))

    def _send_bytes(self, bs):

        with self.__sockets:
            if self.__sockets:
                try:
                    for sock in self.__sockets:
                        sock.sendall(bs)

                except Exception as e:
                    raise secs.Secs1CommunicatorError(e)

            else:
                raise secs.Secs1CommunicatorError("Not connected")

    def _reading(self, sock):

        #TODO
        #reading

        pass


class Secs1OnTcpIpCommunicator(AbstractSecs1OnTcpIpCommunicator):

    __DEFAULT_RECONNECT = 5.0

    def __init__(self, ip_address, port, session_id, is_equip, is_master, **kwargs):
        super(Secs1OnTcpIpCommunicator, self).__init__(session_id, is_equip, is_master, **kwargs)

        self._tpe = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        self._ipaddr = (ip_address, port)

        self.__waiting_cdts = list()
        self.__open_close_local_lock = threading.Lock()

        self.reconnect = kwargs.get('reconnect', self.__DEFAULT_RECONNECT)

    @property
    def reconnect(self):
        pass

    @reconnect.getter
    def reconnect(self):
        return self.__reconnect

    @reconnect.setter
    def reconnect(self, val):
        self.__reconnect = float(val)

    def _open(self):

        with self.__open_close_local_lock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")
            self._set_opened()

        def _connecting():

            cdt = threading.Condition()

            try:
                self.__waiting_cdts.append(cdt)

                while self.is_open:

                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

                            try:
                                self._add_socket(sock)
                                sock.connect(self._ipaddr)
                                self._reading(sock)

                            finally:
                                self._remove_socket(sock)

                    except Exception as e:
                        if self.is_open:
                            self._put_error(e)
                        
                    if self.is_closed:
                        return None

                    with cdt:
                        cdt.wait(self.reconnect)                  

            finally:
                self.__waiting_cdts.remove(cdt)

        self.__tpe.submit(_connecting)

    def _close(self):
        with self.__open_close_local_lock:
            if self.is_closed:
                return
            self._set_closed()

        for cdt in self.__waiting_cdts:
            with cdt:
                cdt.notify_all()

        self.__tpe.shutdown(wait=True, cancel_futures=True)


class Secs1OnTcpIpReceiverCommunicator(AbstractSecs1OnTcpIpCommunicator):

    def __init__(self, ip_address, port, session_id, is_equip, is_master, **kwargs):
        super(Secs1OnTcpIpReceiverCommunicator, self).__init__(session_id, is_equip, is_master, **kwargs)

        self.__tpe = concurrent.futures.ThreadPoolExecutor(max_workers=64)
        self.__ipaddr = (ip_address, port)

        self.__waiting_cdts = list()
        self.__open_close_local_lock = threading.Lock()

    def _open(self):

        with self.__open_close_local_lock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")
            self._set_opened()

        def _open_server():

            #TODO

            pass

        self.__tpe.submit(_open_server)
    
    def _close(self):
        with self.__open_close_local_lock:
            if self.is_closed:
                return
            self._set_closed()

        for cdt in self.__waiting_cdts:
            with cdt:
                cdt.notify_all()

        self.__tpe.shutdown(wait=True, cancel_futures=True)

