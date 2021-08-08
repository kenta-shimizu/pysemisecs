import unittest
import secs

class Test(unittest.TestCase):

    def __build_passive(self):
        return secs.HsmsSsPassiveCommunicator(
            ip_address='127.0.0.1',
            port=5000,
            session_id=10,
            is_equip=True,
            timeout_t3=15.0,
            timeout_t6=5.0,
            timeout_t7=10.0,
            timeout_t8=6.0,
            gem_mdln='MDLN-A',
            gem_softrev='000001',
            gem_clock_type=secs.ClockType.A16,
            name='equip-passive-comm'
        )

    def __build_active(self):
        return secs.HsmsSsActiveCommunicator(
            ip_address='127.0.0.1',
            port=5000,
            session_id=10,
            is_equip=False,
            timeout_t3=15.0,
            timeout_t5=10.0,
            timeout_t6=5.0,
            timeout_t8=6.0,
            gem_clock_type=secs.ClockType.A16,
            name='host-active-comm'
        )

    def __build_equip_master(self):
        return secs.Secs1OnTcpIpCommunicator(
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
            name='equip-master-comm'
        )

    def __build_host_slave(self):
        return secs.Secs1OnTcpIpReceiverCommunicator(
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
            name='host-slave-comm'
        )

    def test_hsmsss_standard(self):

        passive = self.__build_passive()
        active = self.__build_active()

        def _recv_pasv(primary, comm):

            strm = primary.strm
            func = primary.func
            wbit = primary.wbit

            def _sxf0(x):
                comm.reply(primary, x, 0, False)

            try:
                if strm == 1:

                    if func == 1:

                        if wbit:

                            self.assertEqual(1, strm)
                            self.assertEqual(1, func)
                            self.assertTrue(wbit)
                            self.assertIsNone(primary.secs2body)

                            comm.reply(
                                primary,
                                1, 2, False,
                                ('L', [
                                    ('A', 'MDLN-A'),
                                    ('A', '000001')
                                ])
                            )

                    else:
                        if wbit:
                            _sxf0(strm)
                        comm.gem.s9f5(primary)

                else:
                    if wbit:
                        _sxf0(0)
                    comm.gem.s9f3(primary)

            except Exception as e:
                raise e

        def _recv_actv(primary, comm):
            pass
        
        passive.add_recv_primary_msg_listener(_recv_pasv)
        active.add_recv_primary_msg_listener(_recv_actv)

        with passive:
            passive.open()

            with active:
                active.open_and_wait_until_communicating()

                try:

                    reply_s1f2 = active.send(1, 1, True)
                    self.assertEqual(1, reply_s1f2.strm)
                    self.assertEqual(2, reply_s1f2.func)
                    self.assertEqual(False, reply_s1f2.wbit)
                    self.assertEqual('L', reply_s1f2.secs2body.type)
                    self.assertEqual(2, len(reply_s1f2.secs2body))

                    reply_none = active.send(1, 1, False)
                    self.assertIsNone(reply_none)

                    reply_s1f0 = active.send(1, 99, True)
                    self.assertEqual(1, reply_s1f0.strm)
                    self.assertEqual(0, reply_s1f0.func)
                    self.assertEqual(False, reply_s1f0.wbit)
                    self.assertIsNone(reply_s1f0.secs2body)

                    reply_s0f0 = active.send(99, 99, True)
                    self.assertEqual(0, reply_s0f0.strm)
                    self.assertEqual(0, reply_s0f0.func)
                    self.assertEqual(False, reply_s0f0.wbit)
                    self.assertIsNone(reply_s0f0.secs2body)

                except Exception as e:
                    raise e

    def test_hsmsss_sml(self):

        passive = self.__build_passive()
        active = self.__build_active()

        def _recv_pasv(primary, comm):
            pass

        def _recv_actv(primary, comm):

            strm = primary.strm
            func = primary.func
            wbit = primary.wbit

            try:
                if strm == 5:
                    if func == 1:
                        if wbit:

                            self.assertEqual(5, strm)
                            self.assertEqual(1, func)
                            self.assertTrue(wbit)
                            self.assertEqual('L', primary.secs2body.type)
                            self.assertEqual('B', primary.secs2body[0].type)
                            self.assertEqual(b'\x81', primary.secs2body[0].value)
                            self.assertEqual(b'\x81', primary.secs2body.get_value(0))
                            self.assertEqual(0x81, primary.secs2body[0][0])
                            self.assertEqual(0x81, primary.secs2body.get_value(0, 0))
                            self.assertEqual('U2', primary.secs2body[1].type)
                            self.assertEqual((1001, ), primary.secs2body[1].value)
                            self.assertEqual((1001, ), primary.secs2body.get_value(1))
                            self.assertEqual(1001, primary.secs2body[1][0])
                            self.assertEqual(1001, primary.secs2body.get_value(1, 0))
                            self.assertEqual('A', primary.secs2body[2].type)
                            self.assertEqual('ON FIRE', primary.secs2body[2].value)
                            self.assertEqual('ON FIRE', primary.secs2body.get_value(2))
                            self.assertEqual(3, len(primary.secs2body))

                            comm.reply_sml(primary, 'S5F2 <B 0x0>.')

            except Exception as e:
                raise e
        
        passive.add_recv_primary_msg_listener(_recv_pasv)
        active.add_recv_primary_msg_listener(_recv_actv)

        with passive:
            passive.open()

            with active:
                active.open_and_wait_until_communicating()

                try:
                    reply = passive.send_sml(
                        'S5F1 W' +
                        '<L'+
                        '  <B 0x81>' +
                        '  <U2 1001>' +
                        '  <A "ON FIRE">' +
                        '>.'
                    )

                    self.assertEqual(5, reply.strm)
                    self.assertEqual(2, reply.func)
                    self.assertFalse(reply.wbit)
                    self.assertEqual('B', reply.secs2body.type)
                    self.assertEqual(0, reply.secs2body[0])
                    self.assertEqual(0, reply.secs2body.get_value(0))

                except Exception as e:
                    raise e

    def test_hsmsss_gem(self):

        passive = self.__build_passive()
        active = self.__build_active()

        def _recv_pasv(primary, comm):

            strm = primary.strm
            func = primary.func
            wbit = primary.wbit
            
            def _sxf0(x):
                comm.reply(primary, x, 0, False)

            try:
                if strm == 1:

                    if func == 13:
                        if wbit:
                            comm.gem.s1f14(primary, secs.COMMACK.OK)

                    elif func == 15:
                        if wbit:
                            comm.gem.s1f16(primary)

                    elif func == 17:
                        if wbit:
                            comm.gem.s1f18(primary, secs.ONLACK.OK)

                    else:
                        if wbit:
                            _sxf0(strm)
                        comm.gem.s9f5(primary)


                elif strm == 2:

                    if func == 31:
                        if wbit:
                            comm.gem.s2f32(primary, secs.TIACK.OK)

                    else:
                        if wbit:
                            _sxf0(strm)
                        comm.get.s9f5(primary)

                else:
                    if wbit:
                        _sxf0(strm)
                    comm.get.s9f3(primary)

            except Exception as e:
                raise e

        def _recv_actv(primary, comm):

            strm = primary.strm
            func = primary.func
            wbit = primary.wbit

            try:
                if strm == 2:
                    if func == 17:
                        if wbit:
                            comm.gem.s2f18_now(primary)

            except Exception as e:
                raise e

        passive.add_recv_primary_msg_listener(_recv_pasv)
        active.add_recv_primary_msg_listener(_recv_actv)

        with passive:
            passive.open()

            with active:
                active.open_and_wait_until_communicating()

                try:
                    commack = active.gem.s1f13()
                    self.assertEqual(secs.COMMACK.OK, commack)

                    onlack = active.gem.s1f17()
                    self.assertEqual(secs.ONLACK.OK, onlack)

                    tiack = active.gem.s2f31_now()
                    self.assertEqual(secs.TIACK.OK, tiack)

                    clock = passive.gem.s2f17()
                    self.assertEqual(16, len(clock.to_a16()))

                    oflack = active.gem.s1f15()
                    self.assertEqual(secs.OFLACK.OK, oflack)

                except Exception as e:
                    raise e

    def test_secs1_gem(self):

        secs1c = self.__build_equip_master()
        secs1r = self.__build_host_slave()

        def _recv_equip_master(primary, comm):

            strm = primary.strm
            func = primary.func
            wbit = primary.wbit
            
            def _sxf0(x):
                comm.reply(primary, x, 0, False)

            try:
                if strm == 1:

                    if func == 13:
                        if wbit:
                            comm.gem.s1f14(primary, secs.COMMACK.OK)

                    elif func == 15:
                        if wbit:
                            comm.gem.s1f16(primary)

                    elif func == 17:
                        if wbit:
                            comm.gem.s1f18(primary, secs.ONLACK.OK)

                    else:
                        if wbit:
                            _sxf0(strm)
                        comm.gem.s9f5(primary)


                elif strm == 2:

                    if func == 31:
                        if wbit:
                            comm.gem.s2f32(primary, secs.TIACK.OK)

                    else:
                        if wbit:
                            _sxf0(strm)
                        comm.get.s9f5(primary)

                else:
                    if wbit:
                        _sxf0(strm)
                    comm.get.s9f3(primary)

            except Exception as e:
                raise e

        def _recv_host_slave(primary, comm):

            strm = primary.strm
            func = primary.func
            wbit = primary.wbit

            try:
                if strm == 1:
                    if func == 13:
                        if wbit:
                            comm.gem.s1f14(primary, secs.COMMACK.OK)

                elif strm == 2:
                    if func == 17:
                        if wbit:
                            comm.gem.s2f18_now(primary)

                elif strm == 6:
                    if func == 3:
                        self.assertEqual(9, len(primary.secs2body))
                        self.assertEqual(10, len(primary.secs2body[0]))

            except Exception as e:
                raise e

        secs1c.add_recv_primary_msg_listener(_recv_equip_master)
        secs1r.add_recv_primary_msg_listener(_recv_host_slave)

        with secs1r:
            secs1r.open()

            with secs1c:
                secs1c.open_and_wait_until_communicating()

                secs1r.open_and_wait_until_communicating()

                try:
                    commack = secs1r.gem.s1f13()
                    self.assertEqual(secs.COMMACK.OK, commack)

                    onlack = secs1r.gem.s1f17()
                    self.assertEqual(secs.ONLACK.OK, onlack)

                    tiack = secs1r.gem.s2f31_now()
                    self.assertEqual(secs.TIACK.OK, tiack)

                    clock = secs1c.gem.s2f17()
                    self.assertEqual(16, len(clock.to_a16()))

                    secs1c.send(
                        6, 3, False,
                        ('L', [
                            ('U4', [101, 102, 103, 104, 105, 106, 107, 108, 109, 110]),
                            ('U4', [201, 202, 203, 204, 205, 206, 207, 208, 209, 210]),
                            ('U4', [301, 302, 303, 304, 305, 306, 307, 308, 309, 310]),
                            ('U4', [401, 402, 403, 404, 405, 406, 407, 408, 409, 410]),
                            ('U4', [501, 502, 503, 504, 505, 506, 507, 508, 509, 510]),
                            ('U4', [601, 602, 603, 604, 605, 606, 607, 608, 609, 610]),
                            ('U4', [701, 702, 703, 704, 705, 706, 707, 708, 709, 710]),
                            ('U4', [801, 802, 803, 804, 805, 806, 807, 808, 809, 810]),
                            ('U4', [901, 902, 903, 904, 905, 906, 907, 908, 909, 910])
                        ])
                        )

                    oflack = secs1r.gem.s1f15()
                    self.assertEqual(secs.OFLACK.OK, oflack)

                except Exception as e:
                    raise e

if __name__ == '__main__':
    unittest.main()
