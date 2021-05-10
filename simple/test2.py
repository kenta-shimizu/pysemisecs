import threading
import time
import secs

if __name__ == '__main__':

    rlock = threading.RLock()

    def _echo(v):
        with rlock:
            print(v)
    
    _echo("try-python3")

    ip_address = '127.0.0.1'
    port = 5000
    session_id = 100

    def _hsmsss_state(comm, state):
        with rlock:
            _echo(comm.get_name() + ': state: ' + state)

    def _sended(comm, msg):
        with rlock:
            _echo(comm.get_name() + ': sended')
            _echo(msg)

    def _recv(comm, msg):
        with rlock:
            _echo(comm.get_name() + ': received')
            _echo(msg)

    def _error(comm, e):
        with rlock:
            _echo(comm.get_name() + ': ' + repr(e))

    with secs.HsmsSsPassiveCommunicator(
        ip_address, port, session_id, True,
        name='equip-comm') as passive:

        passive.add_hsmsss_communicate_listener(_hsmsss_state)
        passive.add_sended_msg_listener(_sended)
        passive.add_recv_all_msg_listener(_recv)
        passive.add_error_listener(_error)

        passive.open()

        active = secs.HsmsSsActiveCommunicator(
            ip_address, port, session_id, False,
            name='host-comm')

        active.add_hsmsss_communicate_listener(_hsmsss_state)
        active.add_sended_msg_listener(_sended)
        active.add_recv_all_msg_listener(_recv)
        active.add_error_listener(_error)

        active.open_and_wait_until_communicating()

        active.send_linktest_req()

        time.sleep(1.0)

        active.close()
        
        time.sleep(1.0)
        _echo('active-closed')

    time.sleep(1.0)
    _echo("reach-end")
