import secs


class AbstractSecs1Communicator(secs.AbstractSecsCommunicator):

    _DEFAULT_RETRY = 3

    def __init__(self, session_id, is_equip, is_master, **kwargs):
        super(AbstractSecs1Communicator, self).__init__(session_id, is_equip, **kwargs)
        self.set_master_mode(is_master)
        self.set_retry(kwargs.get('retry', self._DEFAULT_RETRY))

    def set_master_mode(self, is_master):
        self._is_master = bool(is_master)

    def set_retry(self, v):
        if v is None:
            raise TypeError("retry-value require not None")
        if v >= 0:
            self._retry = v
        else:
            raise ValueError("retry-value require >= 0")
    
    def _open(self):
        pass

    def _close(self):
        with self._open_close_rlock:
            if self.is_closed():
                return
            self._set_closed()

    def _send(self, strm, func, wbit, secs2body, system_bytes, device_id):
        return self.send_secs1_msg(
            secs.Secs1Message(strm, func, wbit, secs2body, system_bytes, device_id, self._is_equip))

    def send_secs1_msg(self, msg):

        timeout_tx = self._timeout_t3 if msg.has_wbit() else -1.0

        #TODO
        #send

        if timeout_tx > 0.0:

            #TODO
            #wait-reply
            return 1
        
        else:
            return None
