import doctest
import io
import sys
import unittest

if sys.version_info[0] >= 3:
    from test import support as test_support
    from pikl import pickletools_3 as pt
else:
    from test import test_support
    from pikl import pickletools_2 as pt


class PickleToolsReadTest(unittest.TestCase):
    def test_read_uint1_truncated(self):
        self.assertRaises(ValueError, pt.read_uint1, io.BytesIO(b''))

    def test_read_uint2_truncated(self):
        self.assertRaises(ValueError, pt.read_uint2, io.BytesIO(b''))
        self.assertRaises(ValueError, pt.read_uint2, io.BytesIO(b'\x00'))


    def test_read_int4_truncated(self):
        self.assertRaises(ValueError, pt.read_int4, io.BytesIO(b''))
        self.assertRaises(ValueError, pt.read_int4, io.BytesIO(b'\x00'))
        self.assertRaises(ValueError, pt.read_int4, io.BytesIO(b'\x00\x00\x00'))

    @unittest.skipIf(not hasattr(pt, 'read_uint4'),
                     "uint4 argument not available in Python 2.x")
    def test_read_uint4_truncated(self):
        self.assertRaises(ValueError, pt.read_uint4, io.BytesIO(b''))
        self.assertRaises(ValueError, pt.read_uint4, io.BytesIO(b'\x00'))
        self.assertRaises(ValueError, pt.read_uint4, io.BytesIO(b'\x00\x00\x00'))

    def test_read_stringnl_lopsided_quote(self):
        self.assertRaises(ValueError, pt.read_stringnl, io.BytesIO(b'"abc\n'))
        self.assertRaises(ValueError, pt.read_stringnl, io.BytesIO(b"'abc\n"))
        self.assertRaises(ValueError, pt.read_stringnl, io.BytesIO(b'\n'))

    def test_read_string4_negative_length(self):
        self.assertRaises(ValueError,
                          pt.read_string4, io.BytesIO(b'\xff\xff\xff\xffabc'))

    def test_read_string1_truncated(self):
        self.assertRaises(ValueError, pt.read_string1, io.BytesIO(b'\x04abc'))

    @unittest.skipIf(not hasattr(pt, 'read_bytes1'),
                     "bytes1 argument not available in Python 2.x")
    def test_read_bytes1_truncated(self):
        self.assertRaises(ValueError, pt.read_bytes1, io.BytesIO(b'\x04abc'))

    @unittest.skipIf(not hasattr(pt, 'read_bytes4'),
                     "bytes4 argument not available in Python 2.x")
    def test_read_bytes4_negative_length(self):
        self.assertRaises(ValueError,
                          pt.read_bytes4, io.BytesIO(b'\xff\xff\xff\xffabc'))

    def test_read_unicodestringnl(self):
        self.assertRaises(ValueError,
                          pt.read_unicodestringnl, io.BytesIO(b''))
        self.assertRaises(ValueError,
                          pt.read_unicodestringnl, io.BytesIO(b'abc'))

    def test_read_decimalnl_short(self):
        self.assertEqual(pt.read_decimalnl_short(io.BytesIO(b"00\n")), False)
        self.assertEqual(pt.read_decimalnl_short(io.BytesIO(b"01\n")), True)

    def test_read_decimalnl_long(self):
        i = pt.read_decimalnl_long(io.BytesIO(b"0L\n"))
        self.assertEqual(i, 0)
        if sys.version_info[0] >= 3:
            self.assertIsInstance(i, int)
        else:
            self.assertIsInstance(i, long)

    def test_read_float8_truncated(self):
        self.assertRaises(ValueError, pt.read_float8, io.BytesIO(b""))

    def test_read_long1_truncated(self):
        self.assertRaises(ValueError, pt.read_long1, io.BytesIO(b"\x01"))

    def test_read_long4_negative_length(self):
        self.assertRaises(ValueError,
                          pt.read_long4, io.BytesIO(b"\xff\xff\xff\xff"))

    def test_read_long4_truncated(self):
        self.assertRaises(ValueError,
                          pt.read_long4, io.BytesIO(b"\x02\x00\x00\x00\xff"))


class PickleToolsOptimizeTest(unittest.TestCase):
    # pickle.dumps(["abc", "abc"], proto)

    def test_optimize_proto_0(self):
        self.assertEqual(pt.optimize(b"(lp0\nS'abc'\np1\nag1\na."),
                         b"(lS'abc'\np1\nag1\na.")

    def test_optimize_proto_1(self):
        self.assertEqual(pt.optimize(b']q\x00(U\x03abcq\x01h\x01e.'),
                         b'](U\x03abcq\x01h\x01e.')

    def test_optimize_proto_2(self):
        self.assertEqual(pt.optimize(b'\x80\x02]q\x00(U\x03abcq\x01h\x01e.'),
                         b'\x80\x02](U\x03abcq\x01h\x01e.')


def test_suite():
    return unittest.TestSuite([
        unittest.makeSuite(PickleToolsReadTest),
        unittest.makeSuite(PickleToolsOptimizeTest),
        doctest.DocTestSuite(pt),
    ])

if __name__ == '__main__':
    test_support.run_unittest(test_suite())
