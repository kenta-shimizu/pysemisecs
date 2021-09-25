"""Protocol Convert Example

HSMS-SS <-> SECS-I converter example.

Connection diagram

HSMS-SS-ACTIVE <-> HSMS-SS-PASSIVE <-> SECS-I-on-TCP/IP <-> SECS-I-on-TCP/IP-Receiver
(HOST)             (Convert-SIDE-A)    (Convert-SIDE-B)     (EQUIP)

This example is

From HOST to EQUIP via Protocol-converter.
send S1F13, receive S1F14
send S1F17, receive S1F18

From EQUIP to HOST via Protocol-converter.
receive S2F17, reply S2F18

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


def _echo(v):
    print(v)

if __name__ == '__main__':

    _echo("start")

    side_a = secs.HsmsSsPassiveCommunicator(
        ip_address='127.0.0.1',
        port=5000,
        session_id=10,
        is_equip=True,
        timeout_rebind=1.0)

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
            gem_softrev='000001',
            rebind=1.0) as equip:
            
            def _equip_recv(msg, comm):
                if msg.device_id != comm.device_id:
                    comm.gem.s9f1(msg)
                    return
                
                if msg.strm == 1:
                    if msg.func == 13:
                        if msg.wbit:
                            comm.gem.s1f14(msg, secs.COMMACK.OK)
                    elif msg.func == 17:
                        if msg.wbit:
                            comm.gem.s1f18(msg, secs.ONLACK.OK)
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
                timeout_t5=1.0,
                gem_clock_type=secs.ClockType.A16,
                name='HOST') as host:

                def _host_recv(msg, comm):
                    if msg.device_id != comm.device_id:
                        comm.gem.s9f1(msg)
                        return
                    
                    if msg.strm == 2:
                        if msg.func == 17:
                            if msg.wbit:
                                comm.gem.s2f18_now(msg)
                        else:
                            if msg.wbit:
                                comm.reply(msg, msg.strm, 0, False)
                            comm.gem.s9f5(msg)
                    else:
                        if msg.wbit:
                            comm.reply(msg, 0, 0, False)
                        comm.gem.s9f3(msg)
                
                host.add_recv_primary_msg_listener(_host_recv)

                def _hsmsss_state(state, comm):
                    _echo(comm.name + ' state: ' + str(state))

                def _recv_msg(msg, comm):
                    _echo(comm.name + ' recv: ' + str(msg))

                def _sended_msg(msg, comm):
                    _echo(comm.name + ' sended: ' + str(msg))
                
                def _error(e, comm):
                    _echo(comm.name + ' error: ' + str(e))
                
                host.add_hsmsss_communicate_listener(_hsmsss_state)
                host.add_recv_all_msg_listener(_recv_msg)
                host.add_sended_msg_listener(_sended_msg)
                host.add_error_listener(_error)

                host.open_and_wait_until_communicating()
                
                # from HOST to EQUIP send S1F13
                host.gem.s1f13()
                host.gem.s1f17()

                time.sleep(0.1)

                # from EQUIP to HOST send S2F17
                equip.gem.s2f17()
    
    time.sleep(1.0)
    _echo("reach-end")
