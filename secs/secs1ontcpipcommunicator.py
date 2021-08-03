import threading
import socket
import secs


class AbstractSecs1OnTcpIpCommunicator(secs.AbstractSecs1Communicator):

    def __init__(self, device_id, is_equip, is_master, **kwargs):
        super(AbstractSecs1OnTcpIpCommunicator, self).__init__(device_id, is_equip, is_master, **kwargs)

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

        with self.__lock_sockets:
            if self.__sockets:
                try:
                    for sock in self.__sockets:
                        sock.sendall(bs)

                except Exception as e:
                    raise secs.Secs1CommunicatorError(e)

            else:
                raise secs.Secs1CommunicatorError("Not connected")

    def _reading(self, sock):
        try:
            while self.is_open:
                bs = sock.recv(4096)
                if bs:
                    self._put_recv_bytes(bs)
                else:
                    return

        except Exception as e:
            if self.is_open:
                self._put_error(e)

    def _interruptable_reading(self, sock, cdt):

        def _f():
            self._reading(sock)
            with cdt:
                cdt.notify_all()

        threading.Thread(target=_f, daemon=True).start()

        with cdt:
            cdt.wait()


class Secs1OnTcpIpCommunicator(AbstractSecs1OnTcpIpCommunicator):

    __DEFAULT_RECONNECT = 5.0

    def __init__(self, ip_address, port, device_id, is_equip, is_master, **kwargs):
        super(Secs1OnTcpIpCommunicator, self).__init__(device_id, is_equip, is_master, **kwargs)

        self._ipaddr = (ip_address, port)

        self.__cdts = list()
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
                self.__cdts.append(cdt)

                while self.is_open:

                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

                            try:
                                self._add_socket(sock)
                                sock.connect(self._ipaddr)

                                self._interruptable_reading(sock, cdt)

                            finally:
                                self._remove_socket(sock)

                                try:
                                    sock.shutdown(socket.SHUT_RDWR)

                                except Exception as e:
                                    if self.is_open:
                                        self._put_error(e)

                    except Exception as e:
                        if self.is_open:
                            self._put_error(e)
                        
                    if self.is_closed:
                        return

                    with cdt:
                        cdt.wait(self.reconnect)

            finally:
                self.__cdts.remove(cdt)

        threading.Thread(target=_connecting, daemon=True).start()

    def _close(self):
        with self.__open_close_local_lock:
            if self.is_closed:
                return
            self._set_closed()

        for cdt in self.__cdts:
            with cdt:
                cdt.notify_all()


class Secs1OnTcpIpReceiverCommunicator(AbstractSecs1OnTcpIpCommunicator):

    DEFAULT_REBIND = 5.0

    def __init__(self, ip_address, port, device_id, is_equip, is_master, **kwargs):
        super(Secs1OnTcpIpReceiverCommunicator, self).__init__(device_id, is_equip, is_master, **kwargs)

        self.__ipaddr = (ip_address, port)

        self.__cdts = list()
        self.__open_close_local_lock = threading.Lock()

        self.rebind = kwargs.get('rebind', self.__DEFAULT_REBIND)

    @property
    def rebind(self):
        pass

    @rebind.getter
    def rebind(self):
        return self.__rebind

    @rebind.setter
    def rebind(self, val):
        self.__rebind = float(val)

    def _open(self):

        with self.__open_close_local_lock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")
            self._set_opened()

        def _open_server():

            cdt = threading.Condition()

            try:
                self.__cdts.append(cdt)

                while self.is_open:

                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

                            server.bind(self.__ipaddr)
                            server.listen()

                            while self.is_open:
                                sock = (server.accept())[0]
                                threading.Thread(target=self.__accept, args=(sock,), daemon=True).start()

                    except Exception as e:
                        if self.is_open:
                            self._put_error(e)

                    if self.is_closed:
                        return

                    with cdt:
                        cdt.wait(self.rebind)

            finally:
                self.__cdts.remove(cdt)

        threading.Thread(target=_open_server, daemon=True)

    def __accept(self, sock):

        with sock:

            cdt = threading.Condition()

            try:
                self._add_socket(sock)
                self.__cdts.append(cdt)

                self._interruptable_reading(sock, cdt)

            finally:
                self._remove_socket(sock)
                self.__cdts.remove(cdt)

                try:
                    sock.shutdown(socket.SHUT_RDWR)

                except Exception as e:
                    if self.is_open:
                        self._put_error(e)

    def _close(self):
        with self.__open_close_local_lock:
            if self.is_closed:
                return
            self._set_closed()

        for cdt in self.__cdts:
            with cdt:
                cdt.notify_all()

