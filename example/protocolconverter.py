"""Protocol Convert Example

HSMS-SS-ACTIVE <-> HSMS-SS-PASSIVE <-> SECS-I-on-TCP/IP <-> SECS-I-on-TCP/IP-Receiver
(HOST)             (Convert-SIDE-A)    (Convert-SIDE-B)     (EQUIP)

From HOST
send S1F13, receive S1F14 (success sample)
send S1F99, receive S1F0, S9F5 (failed sample)
send S2F99, receive S0F0, S9F3 (failed sample)
"""

import secs
import time

class ProtocolConverter:

    def __init__(self, side_a, side_b):
        """ProtocolConverter

        Args:
            side_a (secs.AbstractSecsCommunicator): Side_A
            side_b (secs.AbstractSecsCommunicator): Side_B
        """
        self.__a = side_a
        self.__b = side_b

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    def open(self):

        def _recv_a(msg):

            def _send():
                return self.__b.send(
                    strm=msg.strm,
                    func=msg.func,
                    wbit=msg.wbit,
                    secs2body=msg.secs2body)

            if msg.wbit:
                r = _send()
                self.__a.reply(msg, r.strm, r.func, r.wbit, r.secs2body)

            else:
                _send()
        
        self.__a.add_recv_primary_msg_listener(_recv_a)

        def _recv_b(msg):

            def _send():
                return self.__a.send(
                    strm=msg.strm,
                    func=msg.func,
                    wbit=msg.wbit,
                    secs2body=msg.secs2body)

            if msg.wbit:
                r = _send()
                self.__b.reply(msg, r.strm, r.func, r.wbit, r.secs2body)

            else:
                _send()
        
        self.__b.add_recv_primary_msg_listener(_recv_b)

        self.__a.open()
        self.__b.open()
    
    def close(self):
        self.__a.close()
        self.__b.close()


if __name__ == '__main__':
    print("start")

    side_a = secs.HsmsSsPassiveCommunicator(
        ip_address='127.0.0.1',
        port=5000,
        session_id=10,
        is_equip=True)

    side_b = secs.Secs1OnTcpIpCommunicator(
        ip_address='127.0.0.1',
        port=23000,
        device_id=10,
        is_equip=False,
        is_master=False,
        reconnect=1.0)

    with ProtocolConverter(side_a, side_b):

        with secs.Secs1OnTcpIpReceiverCommunicator(
            ip_address='127.0.0.1',
            port=23000,
            device_id=10,
            is_equip=True,
            is_master=True,
            gem_mdln='MDLN-A',
            gem_softrev='000001') as equip:
            
            def _equip_recv(msg, comm):
                if msg.device_id != comm.device_id:
                    comm.gem.s9f1(msg)
                    return
                
                if msg.strm == 1:
                    if msg.func == 13:
                        if msg.wbit:
                            comm.gem.s1f14(msg, secs.COMMACK.OK)
                    else:
                        if msg.wbit:
                            comm.reply(msg, msg.strm, 0, False)
                        comm.gem.s9f5(msg)
                else:
                    if msg.wbit:
                        comm.reply(msg, 0, 0, False)
                    comm.gem.s9f3(msg)

            equip.add_recv_primary_msg_listener(_equip_recv)

            equip.open_and_wait_until_communicating()

            with secs.HsmsSsActiveCommunicator(
                ip_address='127.0.0.1',
                port=5000,
                session_id=10,
                is_equip=False,
                timeout_t5=1.0) as host:

                def _recv_msg(msg):
                    print('recv: ' + str(msg))

                def _sended_msg(msg):
                    print('sended: ' + str(msg))
                
                host.add_recv_all_msg_listener(_recv_msg)
                host.add_sended_msg_listener(_sended_msg)

                host.open_and_wait_until_communicating()
                
                host.gem.s1f13()
                host.send(1, 99, True)
                host.send(2, 99, True)

                time.sleep(1.0)

    print("reach-end")
