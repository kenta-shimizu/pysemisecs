import threading
import time
import secs

if __name__ == '__main__':

    lock = threading.Lock()

    def _echo(v):
        with lock:
            print(v)
    
    def _tt(a, b):
        # _echo(a)
        _echo(b)
    
    _echo("try-python3")

    # comm = secs.HsmsSsActiveCommunicator('127.0.0.1', 5000, 100, False)
    comm = secs.HsmsSsPassiveCommunicator('127.0.0.1', 5000, 100, True)

    comm.add_recv_primary_msg_listener(_tt)
    comm.add_hsmsss_communicate_listener(_tt)
    comm.add_sended_msg_listener(_tt)
    comm.add_recv_all_msg_listener(_tt)
    comm.add_error_listener(_tt)

    try:
        comm.open_and_wait_until_communicating()

        comm.send_linktest_req()

        comm.send(1, 1, True)

        time.sleep(3.0)
        _echo("time.sleep-3")
        time.sleep(3.0)
        _echo("time.sleep-2")
        time.sleep(3.0)
        _echo("time.sleep-1")

    except Exception as e:
        _echo(e)
    finally:
        comm.close()

    _echo("reach-end")

