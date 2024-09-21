# pysemisecs

## Introduction

This package is SEMI-SECS-communicate implementation on Python3.

## Supports

- SECS-I (SEMI-E4)
- SECS-II (SEMI-E5)
- GEM (SEMI-E30, partially)
- HSMS-SS (SEMI-E37.1)
- [SML (PEER Group)](https://www.peergroup.com/expertise/resources/secs-message-language/)

## Setup

- Most simple way, Download [secs.py](https://raw.githubusercontent.com/kenta-shimizu/pysemisecs/main/simple/secs.py) file

  `import secs`  
  or append codes in `if __name__ == '__main__':`

  If use `Secs1OnPySerialCommunicator`, must install [pySerial](https://pypi.org/project/pyserial/)

- pip install

```bash
  $ pip install git+https://github.com/kenta-shimizu/pysemisecs
```

  Notes: this pip also installs pySerial.

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
        timeout_t8=5.0,
        gem_mdln='MDLN-A',
        gem_softrev='000001',
        gem_clock_type=secs.ClockType.A16,
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
        timeout_t8=5.0,
        gem_clock_type=secs.ClockType.A16,
        name='host-acitve-comm')

    active.open()
```

- For use SECS-I-on-pySerial

  For use, must install [pySerial](https://pypi.org/project/pyserial/)

```python
    secs1p = secs.Secs1OnPySerialCommunicator(
        port='/dev/ttyUSB0',
        baudrate=9600,
        device_id=10,
        is_equip=True,
        is_master=True,
        timeout_t1=1.0,
        timeout_t2=15.0,
        timeout_t3=45.0,
        timeout_t4=45.0,
        gem_mdln='MDLN-A',
        gem_softrev='000001',
        gem_clock_type=secs.ClockType.A16,
        name='equip-master-comm')
    
    secs1p.open()
```

- For use SECS-I-on-TCP/IP

```python
    # This is connect/client type connection.
    # This and 'Secs1OnTcpIpReceiverCommunicator' are a pair.
   
    secs1c = secs.Secs1OnTcpIpCommunicator(
        ip_address='127.0.0.1',
        port=23000,
        device_id=10,
        is_equip=True,
        is_master=True,
        timeout_t1=1.0,
        timeout_t2=15.0,
        timeout_t3=45.0,
        timeout_t4=45.0,
        gem_mdln='MDLN-A',
        gem_softrev='000001',
        gem_clock_type=secs.ClockType.A16,
        name='equip-master-comm')

    secs1c.open()
```

- For use SECS-I-on-TCP/IP-Receiver

```python
    # This is bind/server type connection.
    # This and 'Secs1OnTcpIpCommunicator' are a pair.

    secs1r = secs.Secs1OnTcpIpReceiverCommunicator(
        ip_address='127.0.0.1',
        port=23000,
        device_id=10,
        is_equip=False,
        is_master=False,
        timeout_t1=1.0,
        timeout_t2=15.0,
        timeout_t3=45.0,
        timeout_t4=45.0,
        gem_clock_type=secs.ClockType.A16,
        name='host-slave-comm')

    secs1r.open()
```

  Notes: To shutdown communicator, `.close()` or use a `with` statement.

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

`.send()` is blocking-method.  
Blocking until Reply-Message received.  
Reply-Message has value if W-Bit is `True`, otherwise `None`.  
If T3-Timeout, raise `SecsWaitReplyMessageError`.


## Received Primary-Message, parse, and send Reply-Message

1. Add listener to receive Primary-Message

```python
    def recv_primary_msg(primary_msg, comm):
        # something...

    active.add_recv_primary_msg_listener(recv_primary_msg)
```

2. Parse Message

```python
    # Receive
    # S5F1 W
    # <L
    #   <B 0x81>
    #   <U2 1001>
    #   <A "ON FIRE">
    # >.

    >>> primary_msg.strm
    5
    >>> primary_msg.func
    1
    >>> primary_msg.wbit
    True
    >>> primary_msg.secs2body.type
    L
    >>> primary_msg.secs2body[0].type
    B
    >>> primary_msg.secs2body[0].value
    b'\x81'
    >>> primary_msg.secs2body.get_value(0)
    b'\x81'
    >>> primary_msg.secs2body[0][0]
    129
    >>> primary_msg.secs2body.get_value(0, 0)
    129
    >>> primary_msg.secs2body[1].type
    U2
    >>> primary_msg.secs2body[1].value
    (1001,)
    >>> primary_msg.secs2body[1][0]
    1001
    >>> primary_msg.secs2body.get_value(1, 0)
    1001
    >>> primary_msg.secs2body[2].type
    A
    >>> primary_msg.secs2body[2].value
    ON FIRE
    >>> primary_msg.secs2body.get_value(2)
    ON FIRE
    >>> primary_msg.secs2body[2][:]
    ON FIRE
    >>> primary_msg.secs2body[2][3:7]
    FIRE
    >>> len(primary_msg.secs2body)
    3
    >>> [v.value for v in primary_msg.secs2body]
    [b'\x81', (1001,), 'ON FIRE']
```

3. Send Reply-Message

```python
    # Reply S5F2 <B 0x0>.

    comm.reply(
        primary=primary_msg,
        strm=5,
        func=2,
        wbit=False,
        secs2body=('B', [0x0])
    )
```

## Detect Communicatable-state changed

1. Add listener

```
    def _comm_listener(communicatable, comm):
        if communicatable:
            print('communicated')
        else:
            print('discommunicated')
    
    passive.add_communicate_listener(_comm_listener)
```

## SML

- Send Primary-Message

```python
    reply_msg = active.send_sml('S1F1 W.')
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

Notes: Don't forget a period(.) of ends message.

## GEM

Access from `.gem` property.

### Clock

- Send S2F17 and receive reply, parse to `datetime`

```python
    clock = passive.gem.s2f17()
    dt = clock.to_datetime()
```

- Reply S2F18 Now examples

```python
    active.gem.s2f18_now(primary_s2f17_msg)
    active.gem.s2f18(primary_s2f17_msg, secs.Clock.now())
    active.gem.s2f18(primary_s2f17_msg, secs.Clock(datetime.datetime.now()))
```

- Send S2F31 Now examples

```puthon
    tiack = active.gem.s2f31_now()
    tiack = active.gem.s2f31(secs.Clock.now())
    tiack = active.gem.s2f31(secs.Clock(datetime.datetime.now()))
```

- Receive S2F31, parse to `datetime`, reply S2F32

```python
    clock = secs.Clock.from_ascii(primary_s2f31_msg.secs2body)
    dt = clock.to_datetime()
    passive.gem.s2f32(primary_s2f31_msg, secs.TIACK.OK)
```

TimeFormat (A[12] or A[16]) can be set from `.clock_type` property

```python
    passive.gem.clock_type = secs.ClockType.A12
    passive.gem.clock_type = secs.ClockType.A16
```

### Others

```python
    commack = active.gem.s1f13()
    oflack  = active.gem.s1f15()
    onlack  = active.gem.s1f17()

    passive.gem.s1f14(primary_msg, secs.COMMACK.OK)
    passive.gem.s1f16(primary_msg)
    passive.gem.s1f18(primary_msg, secs.ONLACK.OK)

    passive.gem.s9f1(ref_msg)
    passive.gem.s9f3(ref_msg)
    passive.gem.s9f5(ref_msg)
    passive.gem.s9f7(ref_msg)
    passive.gem.s9f9(ref_msg)
    passive.gem.s9f11(ref_msg)
```
