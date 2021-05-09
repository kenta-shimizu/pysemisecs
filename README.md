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

  building...

- For use HSMS-SS-Active example

  building...

- For use SECS-I example

  building...

## Send Primary-Message and receive Reply-Message

building...

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
