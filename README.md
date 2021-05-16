# pysemisecs

Now buiding...

## Introduction

This library is SEMI-SECS-communicate implementation on Python3.

## Supports

- SECS-I (SEMI-E4) builing...
- SECS-II (SEMI-E5)
- GEM (SEMI-E30, partially)
- HSMS-SS (SEMI-E37.1)
- [SML (PEER Group)](https://www.peergroup.com/expertise/resources/secs-message-language/)

## Setup

- Most simple way, Download [secs.py](https://raw.githubusercontent.com/kenta-shimizu/pysemisecs/main/simple/secs.py) file

  `import secs`  
  or append codes in `if __name__ == '__main__':`

- pip install

  buiding...  

## Create Communicator instance and open

- For use HSMS-SS-Passive example

  ```python
  passive = secs.HsmsSsPassiveCommunicator(
      ip_address='127.0.0.1',
      port=5000,
      session_id=10,
      is_equip=True,
      timeout_t3=45.0,
      timeout_t6=5.0,
      timeout_t7=10.0,
      timeout_t8=6.0,
      name='equip-passive-comm')

  passive.open()
  ```

- For use HSMS-SS-Active example

  ```python
  active = secs.HsmsSsActiveCommunicator(
      ip_address='127.0.0.1',
      port=5000,
      session_id=10,
      is_equip=False,
      timeout_t3=45.0,
      timeout_t5=10.0,
      timeout_t6=5.0,
      timeout_t8=6.0,
      name='host-acitve-comm')

  active.open()
  ```

- For use SECS-I example

  ```python
  # building...
  ```

Notes: To shutdown program, must `AbstractSecsCommunicator.close()`, or use a `with` statement.

## Send Primary-Message and receive Reply-Message

  ```python
  # Send
  # S5F1 W
  # <L
  #   <B 0x81>
  #   <U2 1001>
  #   <A "ON FIRE">
  # >.

  reply_msg = passive.send(
      strm=5,
      func=1,
      wbit=True,
      secs2body=('L', [
          ('B' , [0x81]),
          ('U2', [1001]),
          ('A' , "ON FIRE")
      ])
  )
  ```

  `AbstractSecsCommunicator.send` is blocking-method.  
  Blocking until Reply-Message received.  
  Reply-Message has value if W-Bit is `True`, otherwise `None`  
  If T3-Timeout, raise `SecsWaitReplyMessageError`.


## Received Primary-Message, parse, and send Reply-Message

1. Add listener to receive Primary-Message

  ```python
  def recv_primary_msg(primary_msg, comm):
      # something...

  active.add_recv_primary_msg_listener(recv_primary_msg)
  ```

2. Parse Primary-Message

  ```python
  ```

3. Send Reply-Message

  ```python
  # Reply S5F2 <B 0x0>.

  comm.reply(
      primary=primary_msg,
      strm=5,
      func=2,
      wbit=True,
      secs2body=('B', [0x0])
  )
  ```

## SML

- Send Primary-Message

  ```python
  active.send_sml('S1F1 W.')
  ```

- Send Reply-Message

  ```python
  passive.reply_sml(
      primary_msg,
      'S1F2          ' +
      '<L            ' +
      '  <A "MDLN-A">' +
      '  <A "000001">' +
      '>.            '
  )
  ```

## GEM

Access from `AbstractSecsCommunicator.gem` property.

### Others

```python
passive.gem.s9f1(ref_msg)
passive.gem.s9f3(ref_msg)
passive.gem.s9f5(ref_msg)
passive.gem.s9f7(ref_msg)
passive.gem.s9f9(ref_msg)
passive.gem.s9f11(ref_msg)
```
