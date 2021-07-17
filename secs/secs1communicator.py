import secs
import threading


class Secs1CommunicatorError(secs.SecsCommunicatorError):

    def __init__(self, msg):
        super(Secs1CommunicatorError, self).__init__(msg)


class Secs1SendMessageError(secs.SecsSendMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1SendMessageError, self).__init__(msg, ref_msg)


class Secs1RetryOverError(Secs1SendMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1RetryOverError, self).__init__(msg, ref_msg)


class Secs1WaitReplyMessageError(secs.SecsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1WaitReplyMessageError, self).__init__(msg, ref_msg)


class Secs1TimeoutT3Error(Secs1WaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1TimeoutT3Error, self).__init__(msg, ref_msg)


class MsgAndRecvBytesWaitingQueuing(secs.WaitingQueuing):

    def __init__(self):
        super(MsgAndRecvBytesWaitingQueuing, self).__init__()
        self.__msg_queue = list()

    def put_recv_bytes(self, bs):
        self.puts(bs)

    def entry_msg(self, msg):
        if msg:
            with self._v_lock:
                self.__msg_queue.append(msg)
                with self._v_cdt:
                    self._v_cdt.notify_all()

    def poll_either(self, timeout=None):

        with self._open_close_lock:
            if self._closed or not self._opened:
                return (None, None)

        with self._v_lock:
            if self.__msg_queue:
                return (self.__msg_queue.pop(0), None)

        with self._v_cdt:
            v = self._poll_vv()
            if v is not None:
                return (None, v)

            self._v_cdt.wait(timeout)

        with self._open_close_lock:
            if self._closed or not self._opened:
                return (None, None)

        with self._v_lock:
            if self.__msg_queue:
                return (self.__msg_queue.pop(0), None)

        return (None, self._poll_vv())

    def recv_bytes_garbage(self, timeout):

        with self._open_close_lock:
            if self._closed or not self._opened:
                return;

        with self._v_lock:
            del self._vv[:]

        while True:
            v = self.poll(timeout)
            if v is None:
                return


class SendSecs1MessagePack:

    def __init__(self, msg):
        self.__msg = msg
        self.__present = 0

    def secs1msg(self):
        return self.__msg

    def present_block(self):
        return (self.__msg.to_blocks())[self.__present]

    def next_block(self):
        self.__present += 1

    def reset_block(self):
        self.__present = 0


class Secs1Circuit:

    def __init__(self, parent):
        self._open_close_rlock = threading.RLock()
        self._opened = False
        self._closed = False


    def __circuit(self):

        while True:

            msg, b = self.__msg_and_bytes_queue.poll_either()

            if msg is not None:

                try:
                    pack = SendSecs1MessagePack(msg)

                    count = 0
                    while True:

                        self.__send_bytes(self.__BYTES_ENQ)

                        b = self.__msg_and_bytes_queue.poll(self.__parent.timeout_t2)

                        if b == self.__ENQ:

                            if self.__parent.is_master:

                                b = self.__msg_and_bytes_queue.poll(self.__parent.timeout_t2)

                                if b == self.__EOT:

                                    if self.__sending(pack):

                                        if pack.present_block().ebit:

                                            #TODO
                                            #success sended msg

                                            break

                                        else:

                                            pack.next_block()
                                            count = 0
                                            continue

                                    else:
                                        count += 1

                                else:
                                    count += 1

                            else:

                                self.__receiving()
                                break

                        elif b == self.__EOT:

                            if self.__sending(pack):

                                if pack.present_block().ebit:

                                    #TODO
                                    #success sended msg

                                    break

                                else:

                                    pack.next_block()
                                    count = 0
                                    continue

                            else:
                                count += 1

                        else:
                            count += 1

                        if count > self.__parent.retry:
                            raise Secs1RetryOverError("", msg)

                except Secs1CommunicatorError as e:

                    #TODO
                    pass

                except Secs1SendMessageError as e:

                    #TODO
                    pass

            elif b is not None:

                if b == self.__ENQ:
                    self.__receiving()

            else:
                return

    def __receiving(self):

        try:
            self.__send_bytes(self.__BYTES_EOT)

            bb = list()

            r = self.__msg_and_bytes_queue.put_to_list(
                bb, 0, 1,
                self.__parent.timeout_t2)

            if r <= 0:
                self.__send_bytes(self.__BYTES_NAK)

                #TODO
                #t1-timeout
                    
                return

            bb_size = bb[0]
            if bb_size < 10 or bb_size > 254:
                self.__recv_garbage()
                self.__send_bytes(self.__BYTES_NAK)

                #TODO
                #t1-timeout
                    
                return
            
            i = 1
            m = bb_size + 3

            while i < m:
                r = self.__msg_and_bytes_queue.put_to_list(
                    bb, i, m,
                    self.__parent.timeout_t1)

                if r < 0:
                    self.__send_bytes(self.__BYTES_NAK)

                    #TODO
                    #t1-timeout

                    return
                
                i += r
            
            if self.__sum_check(bb):

                self.__send_bytes(self.__BYTES_ACK)

                block = secs.Secs1MessageBlock(bytes(bb))

                if self.__recv_blocks:

                    if self.__recv_blocks[-1].is_next_block(block):

                        self.__receiving_append(block)

                    else:

                        if self.__recv_blocks[-1].is_sama_block(block):

                            b = self.__msg_and_bytes_queue.poll(self.__parent.timeout_t4)

                            if b == self.__ENQ:
                                self.__receiving()

                        else:

                            del self.__recv_blocks[:]
                            self.__receiving_append(block)

                else:

                    self.__receiving_append(block)

            else:

                self.__recv_garbage()
                self.__send_bytes(self.__BYTES_NAK)

                #TODO
                #t1-timeout

        except Exception as e:

            #TODO
            #put-error

            self.__parent._put_error(e)

            pass

    def __sum_check(self, block):
        a = sum(block[1:-2]) & 0xFFFF
        b = (block[-2] << 8) | block[-1]
        return a == b


    def __receiving_append(self, block):

        self.__recv_blocks.append(block)

        if block.ebit:

            try:
                msg = secs.Secs1Message.from_blocks(self.__recv_blocks)

                #TODO
                #recv-msg

            except secs.Secs1MessageParseError as e:

                #TODO
                pass

            finally:
                del self.__recv_blocks[:]

        else:

            #TODO
            #reset-T3-timer

            b = self.__msg_and_bytes_queue.poll(self.__parent.timeout_t4)

            if b == self.__ENQ:
                self.__receiving()


class AbstractSecs1Communicator(secs.AbstractSecsCommunicator):

    __ENQ = 0x5
    __EOT = 0x4
    __ACK = 0x6
    __NAK = 0x15
    __BYTES_ENQ = bytes([__ENQ])
    __BYTES_EOT = bytes([__EOT])
    __BYTES_ACK = bytes([__ACK])
    __BYTES_NAK = bytes([__NAK])

    __DEFAULT_RETRY = 3

    def __init__(self, session_id, is_equip, is_master, **kwargs):
        super(AbstractSecs1Communicator, self).__init__(session_id, is_equip, **kwargs)
        self.is_master = is_master
        self.retry = kwargs.get('retry', self.__DEFAULT_RETRY)

        self.__msg_and_bytes_queue = MsgAndRecvBytesWaitingQueuing()
        self.__recv_blocks = list()

        self.__recv_all_msg_putter = secs.CallbackQueuing(self._put_recv_all_msg)
        self.__sended_msg_putter = secs.CallbackQueuing(self._put_sended_msg)


    @property
    def is_master(self):
        pass

    @is_master.getter
    def is_master(self):
        return self.__is_master

    @is_master.setter
    def is_master(self, val):
        self.__is_master = bool(val)

    @property
    def retry(self):
        pass

    @retry.getter
    def retry(self):
        return self.__retry
    
    @retry.setter
    def retry(self, val):
        if val is None:
            raise TypeError("retry-value require not None")
        else:
            v = int(val)
            if v >= 0:
                self.__retry = v
            else:
                raise ValueError("retry-value require >= 0")
    
    def _open(self):
        self.__msg_and_bytes_queue.open()
        self.__recv_all_msg_putter.open()
        self.__sended_msg_putter.open()

    def _close(self):
        with self._open_close_rlock:
            if self.is_closed:
                return
            self._set_closed()

        self.__msg_and_bytes_queue.close()
        self.__recv_all_msg_putter.close()
        self.__sended_msg_putter.close()

    def _send(self, strm, func, wbit, secs2body, system_bytes, device_id):
        return self.send_secs1_msg(
            secs.Secs1Message(strm, func, wbit, secs2body, system_bytes, device_id, self.is_equip))

    def send_secs1_msg(self, msg):

        timeout_tx = self.timeout_t3 if msg.wbit else -1.0

        #TODO
        #send

        def _send_block(bs):
            pass

        if timeout_tx > 0.0:

            #TODO
            #wait-reply
            return 1
        
        else:
            return None

    def _put_recv_bytes(self, bs):
        self.__msg_and_bytes_queue.put_recv_bytes(bs)

    def entry_msg(self, msg):
        self.__msg_and_bytes_queue.entry_msg(msg)

    def _send_bytes(self, bs):
        # prototype
        raise NotImplementedError()

    def __circuit(self):

        while True:

            msg, b = self.__msg_and_bytes_queue.poll_either()

            if msg is not None:

                try:
                    pack = SendSecs1MessagePack(msg)

                    count = 0
                    while count <= self.retry:

                        #TODO
                        #next
                        pass
                except Secs1CommunicatorError as e:
                    self._put_error(e)
                except Secs1SendMessageError as e:
                    self._put_error(e)

            elif b is not None:

                if b == self.__ENQ:

                    try:
                        self.__circuit_receiving()
                    except Secs1CommunicatorError as e:
                        self._put_error(e)

            else:
                return

    def __circuit_sending(self, block):

        self._send_bytes(block.to_bytes())

        b = self.__msg_and_bytes_queue.poll(self.timeout_t2)

        if b is None:

            #TODO
            #Timeout-T2
            #put_error
            return False

        elif b == self.__ACK:

            return True

        else:

            #TODO
            #Not recv ACK
            #put_error
            return False

    def __circuit_receiving(self):

        try:
            self.__send_bytes(self.__BYTES_EOT)

            bb = list()

            #TODO

        except Exception as e:
            self._put_error(e)
