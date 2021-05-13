# pysemisecs

Now buiding...

## Introduction

This library is SEMI-SECS-communicate implementation on Python3.

## Supports

- SECS-I (SEMI-E4) builing...
- SECS-II (SEMI-E5)
- GEM (SEMI-E30, partially) building...
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
  passive = HsmsSsPassiveCommunicator(
      ip_address='127.0.0.1',
      port=5000,
      session_id=10,
      is_equip=True,
      timeout_t3=45.0,
      timeout_t6=5.0,
      timeout_t7=10.0,
      timeout_t8=6.0,
      name='equip-passive-comm'
  )
  passive.open()
  ```

- For use HSMS-SS-Active example

  ```python
  active = HsmsSsActiveCommunicator(
      ip_address='127.0.0.1',
      port=5000,
      session_id=10,
      is_equip=False,
      timeout_t3=45.0,
      timeout_t5=10.0,
      timeout_t6=5.0,
      timeout_t8=6.0,
      name='host-acitve-comm'
  )
  active.open()
  ```

- For use SECS-I example

  building...

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

## Received Primary-Message, parse, and send Reply-Message

building...

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

building...
