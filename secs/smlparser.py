import re
import secs


class SmlParseError(Exception):

    def __init__(self, msg):
        super(SmlParseError, self).__init__(msg)


class Secs2BodySmlParseError(SmlParseError):

    def __init__(self, msg):
        super(Secs2BodySmlParseError, self).__init__(msg)


class SmlParser:

    _SML_PATTERN = '[Ss]([0-9]{1,3})[Ff]([0-9]{1,3})\\s*([Ww]?)\\s*((<.*>)?)\\s*\\.$'
    _SML_PROG = re.compile(_SML_PATTERN)

    @classmethod
    def parse(cls, sml_str):
        """parse from SML to Tuple

        Args:
            sml_str (str): SML string.

        Raises:
            Secs2BodySmlParseError: raise if Secs2body parse failed.
            SmlParseError: raise if SML parse failed.

        Returns:
            tuple: (
                int: Stream-Number,
                int: Function-Number),
                bool: W-Bit,
                secs.AbstractSecs2Body: secs2body or None
            )
        """

        s = sml_str.replace('\n', ' ').strip()
        if not s.endswith("."):
            raise SmlParseError("SML not endswith '.'")

        x = cls._SML_PROG.match(s)
        if x is None:
            raise SmlParseError("SML not match")

        body = x.group(4)

        return (
            int(x.group(1)),
            int(x.group(2)),
            len(x.group(3)) > 0,
            cls._parse_body(body) if len(body) > 0 else None
        )

    @classmethod
    def _parse_body(cls, sml_str):

        def _is_ws(v):  # is_white_space
            return (v.encode(encoding='ascii'))[0] <= 0x20

        def _seek_next(s, from_pos, *args):
            p = from_pos
            if len(args) > 0:
                while True:
                    v = s[p]
                    for a in args:
                        if type(a) is str:
                            if v == a:
                                return v, p
                        else:
                            if a(v):
                                return v, p
                    p += 1
            else:
                while True:
                    v = s[p]
                    if _is_ws(v):
                        p += 1
                    else:
                        return v, p

        def _ssbkt(s, from_pos):    # seek size_start_bracket'[' position, return position, -1 if not exist
            v, p = _seek_next(s, from_pos)
            return p if v == '[' else -1

        def _sebkt(s, from_pos):    # seek size_end_bracket']' position, return position
            return (_seek_next(s, from_pos, ']'))[1]

        def _isbkt(s, from_pos):    # seek item_start_bracket'<' position, return position, -1 if not exist
            v, p = _seek_next(s, from_pos)
            return p if v == '<' else -1

        def _iebkt(s, from_pos):    # seek item_end_bracket'>' position, return position
            return (_seek_next(s, from_pos, '>'))[1]

        def _seek_item(s, from_pos):  # seek item_type, return (item_type, shifted_position)
            p_start = (_seek_next(s, from_pos))[1]
            p_end = (_seek_next(s, (p_start + 1), '[', '"', '<', '>', _is_ws))[1]
            return secs.Secs2BodyBuilder.get_item_type_from_sml(s[p_start:p_end]), p_end

        def _f(s, from_pos):

            p = _isbkt(s, from_pos)

            if p < 0:
                raise Secs2BodySmlParseError("Not start < bracket")

            tt, p = _seek_item(s, (p + 1))

            r = _ssbkt(s, p)
            if r >= 0:
                p = _sebkt(s, (r + 1)) + 1
            
            if tt[0] == 'L':
                vv = list()
                while True:
                    v, p = _seek_next(s, p)
                    if v == '>':
                        return tt[5](tt, vv), (p + 1)

                    elif v == '<':
                        r, p = _f(s, p)
                        vv.append(r)

                    else:
                        raise Secs2BodySmlParseError("Not reach LIST end")

            elif tt[0] == 'BOOLEAN':
                r = _iebkt(s, p)
                vv = list()
                for x in s[p:r].strip().split():
                    ux = x.upper()
                    if ux == 'TRUE' or ux == 'T':
                        vv.append(True)
                    elif ux == 'FALSE' or ux == 'F':
                        vv.append(False)
                    else:
                        raise Secs2BodySmlParseError("Not accept, BOOLEAN require TRUE or FALSE")
                return tt[5](tt, vv), (r + 1)

            elif tt[0] == 'A':
                vv = list()
                while True:
                    v, p_start = _seek_next(s, p)
                    if v == '>':
                        return tt[5](tt, ''.join(vv)), (p_start + 1)
 
                    elif v == '"':
                        v, p_end = _seek_next(s, (p_start + 1), '"')
                        vv.append(s[(p_start+1):p_end])
                        p = p_end + 1

                    elif v == '0':
                        if s[p_start + 1] not in ('X', 'x'):
                            raise Secs2BodySmlParseError("Ascii not accept 0xNN")
                        v, p = _seek_next(s, (p_start+2), '"', '>', _is_ws)
                        vv.append(bytes([int(s[(p_start+2):p], 16)]).decode(encoding='ascii'))

                    else:
                        raise Secs2BodySmlParseError("Ascii not reach end")

            elif tt[0] in ('B', 'I1', 'I2', 'I4', 'I8', 'F4', 'F8', 'U1', 'U2', 'U4', 'U8'):
                r = _iebkt(s, p)
                return tt[5](tt, s[p:r].strip().split()), (r + 1)

        try:
            if sml_str is None:
                raise Secs2BodySmlParseError("Not accept None")
            
            ss = str(sml_str).strip()
            lr, lp = _f(ss, 0)
            if len(ss[lp:]) > 0:
                raise Secs2BodySmlParseError("Not reach end, end=" + str(lp) + ", length=" + str(len(ss)))
            return lr

        except TypeError as e:
            raise Secs2BodySmlParseError(str(e))
        except ValueError as e:
            raise Secs2BodySmlParseError(str(e))
        except IndexError as e:
            raise Secs2BodySmlParseError(str(e))
