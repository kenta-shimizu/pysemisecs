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
            while not self.is_closed:
                bs = sock.recv(4096)
                if bs:
                    self._put_recv_bytes(bs)
                else:
                    return

        except Exception as e:
            if not self.is_closed:
                self._put_error(e)


class Secs1OnTcpIpCommunicator(AbstractSecs1OnTcpIpCommunicator):

    __DEFAULT_RECONNECT = 5.0
    __PROTOCOL = 'SECS-I-on-TCP/IP'

    def __init__(self, ip_address, port, device_id, is_equip, is_master, **kwargs):
        super(Secs1OnTcpIpCommunicator, self).__init__(device_id, is_equip, is_master, **kwargs)

        self.__ipaddr = (ip_address, port)

        self.__ths = list()
        self.__cdts = list()

        self.reconnect = kwargs.get('reconnect', self.__DEFAULT_RECONNECT)

    def __str__(self):
        return str({
            'protocol': self.__PROTOCOL,
            'ip_address': (self.__ipaddr[0] + ':' + str(self.__ipaddr[1])),
            'device_id': self.device_id,
            'is_equip': self.is_equip,
            'is_master': self.is_master,
            'name': self.name
        })

    def __repr__(self):
        return repr({
            'protocol': self.__PROTOCOL,
            'ip_address': self.__ipaddr,
            'device_id': self.device_id,
            'is_equip': self.is_equip,
            'is_master': self.is_master,
            'name': self.name
        })

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
        with self._open_close_rlock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")

            def _connecting():

                cdt = threading.Condition()

                try:
                    self.__cdts.append(cdt)

                    while not self.is_closed:

                        try:
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

                                try:
                                    sock.connect(self.__ipaddr)

                                    def _f():
                                        self._reading(sock)
                                        with cdt:
                                            cdt.notify_all()

                                    th_r = threading.Thread(target=_f, daemon=True)
                                    th_r.start()

                                    try:
                                        self.__ths.append(th_r)
                                        self._add_socket(sock)

                                        with cdt:
                                            cdt.wait()
                                    finally:
                                        self.__ths.remove(th_r)
                                        self._remove_socket(sock)

                                finally:
                                    try:
                                        sock.shutdown(socket.SHUT_RDWR)
                                    except Exception as e:
                                        if not self.is_closed:
                                            self._put_error(e)

                        except Exception as e:
                            if not self.is_closed:
                                self._put_error(e)

                        if self.is_closed:
                            return

                        with cdt:
                            cdt.wait(timeout=self.reconnect)

                finally:
                    self.__cdts.remove(cdt)

            th = threading.Thread(target=_connecting, daemon=True)
            th.start()
            self.__ths.append(th)

            super()._open()

            self._set_opened()

    def _close(self):

        if self.is_closed:
            return;

        super()._close()

        self._set_closed()

        for cdt in self.__cdts:
            with cdt:
                cdt.notify_all()

        for th in self.__ths:
            th.join(0.1)


class Secs1OnTcpIpReceiverCommunicator(AbstractSecs1OnTcpIpCommunicator):

    __DEFAULT_REBIND = 5.0
    __PROTOCOL = 'SECS-I-on-TCP/IP-Receiver'

    def __init__(self, ip_address, port, device_id, is_equip, is_master, **kwargs):
        super(Secs1OnTcpIpReceiverCommunicator, self).__init__(device_id, is_equip, is_master, **kwargs)

        self.__ipaddr = (ip_address, port)

        self.__ths = list()
        self.__cdts = list()

        self.rebind = kwargs.get('rebind', self.__DEFAULT_REBIND)

    def __str__(self):
        return str({
            'protocol': self.__PROTOCOL,
            'ip_address': (self.__ipaddr[0] + ':' + str(self.__ipaddr[1])),
            'device_id': self.device_id,
            'is_equip': self.is_equip,
            'is_master': self.is_master,
            'name': self.name
        })

    def __repr__(self):
        return repr({
            'protocol': self.__PROTOCOL,
            'ip_address': self.__ipaddr,
            'device_id': self.device_id,
            'is_equip': self.is_equip,
            'is_master': self.is_master,
            'name': self.name
        })

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
        with self._open_close_rlock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")

            def _open_server():

                cdt = threading.Condition()

                try:
                    self.__cdts.append(cdt)

                    while not self.is_closed:

                        try:
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

                                server.bind(self.__ipaddr)
                                server.listen()

                                while not self.is_closed:

                                    sock = (server.accept())[0]

                                    th_a = threading.Thread(target=self.__accept, args=(sock,), daemon=True)
                                    th_a.start()
                                    self.__ths.append(th_a)

                        except Exception as e:
                            if not self.is_closed:
                                self._put_error(e)

                        if self.is_closed:
                            return

                        with cdt:
                            cdt.wait(timeout=self.rebind)

                finally:
                    self.__cdts.remove(cdt)

            th = threading.Thread(target=_open_server, daemon=True)
            th.start()
            self.__ths.append(th)

            super()._open()

            self._set_opened()

    def __accept(self, sock):

        with sock:

            cdt = threading.Condition()

            try:
                self.__cdts.append(cdt)

                def _f():
                    self._reading(sock)
                    with cdt:
                        cdt.notify_all()

                th_r = threading.Thread(target=_f, daemon=True)
                th_r.start()

                try:
                    self.__ths.append(th_r)
                    self._add_socket(sock)
                    
                    with cdt:
                        cdt.wait()

                finally:
                    self._remove_socket(sock)
                    self.__ths.remove(th_r)

            finally:
                self.__cdts.remove(cdt)

                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except Exception as e:
                    if not self.is_closed:
                        self._put_error(e)

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

