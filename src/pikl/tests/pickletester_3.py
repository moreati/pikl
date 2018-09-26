import io
import unittest
import sys
import copyreg
import weakref
from http.cookies import SimpleCookie
from pikl import pickle_3 as pickle
from pikl import pickletools_3 as pickletools

from test.support import (
    TestFailed, TESTFN, run_with_locale,
    _2G, _4G, bigmemtest,
    )

try:
    from test.support import no_tracing
except ImportError:
    from functools import wraps
    def no_tracing(func):
        if not hasattr(sys, 'gettrace'):
            return func
        @wraps(func)
        def wrapper(*args, **kwargs):
            original_trace = sys.gettrace()
            try:
                sys.settrace(None)
                return func(*args, **kwargs)
            finally:
                sys.settrace(original_trace)
        return wrapper

_PY343 = sys.version_info[:3] >= (3, 4, 3)

from pikl.pickle_3 import bytes_types
from . import _is_pypy

# Tests that try a number of pickle protocols should have a
#     for proto in protocols:
# kind of outer loop.
protocols = range(pickle.LOWEST_PROTOCOL, pickle.HIGHEST_PROTOCOL + 1)
unsupported_protocols = range(0, pickle.LOWEST_PROTOCOL)

ascii_char_size = 1


# Return True if opcode code appears in the pickle, else False.
def opcode_in_pickle(code, pickle):
    for op, dummy, dummy in pickletools.genops(pickle):
        if op.code == code.decode("latin-1"):
            return True
    return False

# Return the number of times opcode code appears in pickle.
def count_opcode(code, pickle):
    n = 0
    for op, dummy, dummy in pickletools.genops(pickle):
        if op.code == code.decode("latin-1"):
            n += 1
    return n


class UnseekableIO(io.BytesIO):
    def peek(self, *args):
        raise NotImplementedError

    def seekable(self):
        return False

    def seek(self, *args):
        raise io.UnsupportedOperation

    def tell(self):
        raise io.UnsupportedOperation


# We can't very well test the extension registry without putting known stuff
# in it, but we have to be careful to restore its original state.  Code
# should do this:
#
#     e = ExtensionSaver(extension_code)
#     try:
#         fiddle w/ the extension registry's stuff for extension_code
#     finally:
#         e.restore()

class ExtensionSaver:
    # Remember current registration for code (if any), and remove it (if
    # there is one).
    def __init__(self, code):
        self.code = code
        if code in copyreg._inverted_registry:
            self.pair = copyreg._inverted_registry[code]
            copyreg.remove_extension(self.pair[0], self.pair[1], code)
        else:
            self.pair = None

    # Restore previous registration for code.
    def restore(self):
        code = self.code
        curpair = copyreg._inverted_registry.get(code)
        if curpair is not None:
            copyreg.remove_extension(curpair[0], curpair[1], code)
        pair = self.pair
        if pair is not None:
            copyreg.add_extension(pair[0], pair[1], code)

STDLIB_EXTENSIONS = [
    ("builtins", "Ellipsis"),
    ("builtins", "NotImplemented"),
    ("builtins", "bytearray"),
    ("builtins", "bytes"),
    # DATA2 pickle assumes that complex has extension_code 4
    ("builtins", "complex"),
    ("builtins", "frozenset"),
    ("builtins", "object"),
    ("builtins", "range"),
    ("builtins", "set"),
    ("builtins", "str"),
    ("builtins", "unicode"),
    ("_codecs", "encode"),  # Used by pikl.binary()
    #("array", "array"),
    # collections?
    ("copyreg", "_reconstructor"),  # Used by object.__reduce__()
    ("http.cookies", "Morsel"),
    ("http.cookies", "SimpleCookie"),
    #("datetime", "date"),
    #("datetime", "datetime"),
    #("datetime", "time"),
    #("datetime", "timedelta"),
    #("datetime", "tzinfo"),
    #("decimal", "Decimal"),
    #("fractions", "Fractions"),
    ("os", "stat_result"),
    ("os", "statvfs_result"),
    ("time", "struct_time"),
]

for code, (module, name) in enumerate(STDLIB_EXTENSIONS, start=1):
    copyreg.add_extension(module, name, code)
del code
del module
del name

class C:
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

class D(C):
    def __init__(self, arg):
        pass

class E(C):
    def __getinitargs__(self):
        return ()

import __main__
__main__.C = C
C.__module__ = "__main__"
__main__.D = D
D.__module__ = "__main__"
__main__.E = E
E.__module__ = "__main__"

# FIXME This changes the global extension registry, ideally each Pickler
#       object would have it's own extension registry.
# NB DATA2 pickle assumes that C has extension_code 240
extension_codes = iter(range(240, 1024))
copyreg.add_extension("__main__", "C", next(extension_codes))
copyreg.add_extension("__main__", "D", next(extension_codes))
copyreg.add_extension("__main__", "E", next(extension_codes))

class myint(int):
    def __init__(self, x):
        self.str = str(x)

copyreg.add_extension(__name__, "myint", next(extension_codes))

class initarg(C):

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __getinitargs__(self):
        return self.a, self.b

copyreg.add_extension(__name__, "initarg", next(extension_codes))

class metaclass(type):
    pass

class use_metaclass(object, metaclass=metaclass):
    pass

copyreg.add_extension(__name__, "use_metaclass", next(extension_codes))

class pickling_metaclass(type):
    def __eq__(self, other):
        return (type(self) == type(other) and
                self.reduce_args == other.reduce_args)

    def __reduce__(self):
        return (create_dynamic_class, self.reduce_args)

def create_dynamic_class(name, bases):
    result = pickling_metaclass(name, bases, dict())
    result.reduce_args = (name, bases)
    return result

copyreg.add_extension(__name__, "create_dynamic_class", next(extension_codes))

# DATA2 is the pickle we expect, for
# the object returned by create_data().

DATA2 = (
    b'\x80\x02]q\x00(K\x00\x8a\x01\x01G@\x00\x00\x00\x00\x00\x00\x00'
    b'\x82\x05G@\x08\x00\x00\x00\x00\x00\x00G\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x86q\x01Rq\x02K\x01J\xff\xff\xff\xffK\xffJ\x01\xff\xff'
    b'\xffJ\x00\xff\xff\xffM\xff\xffJ\x01\x00\xff\xffJ\x00\x00\xff\xffJ'
    b'\xff\xff\xff\x7fJ\x01\x00\x00\x80J\x00\x00\x00\x80(U\x03abcq\x03h'
    b'\x03(\x82\xf0oq\x04}q\x05(U\x03fooq\x06K\x01U\x03barq\x07K\x02ubh'
    b'\x04tq\x08h\x08K\x05e.'
)

# Disassembly of DATA2.
DATA2_DIS = """\
    0: \x80 PROTO      2
    2: ]    EMPTY_LIST
    3: q    BINPUT     1
    5: (    MARK
    6: K        BININT1    0
    8: \x8a     LONG1      1L
   11: G        BINFLOAT   2.0
   20: \x82     EXT1       5
   22: G        BINFLOAT   3.0
   31: G        BINFLOAT   0.0
   40: \x86     TUPLE2
   41: R        REDUCE
   42: q        BINPUT     2
   44: K        BININT1    1
   46: J        BININT     -1
   51: K        BININT1    255
   53: J        BININT     -255
   58: J        BININT     -256
   63: M        BININT2    65535
   66: J        BININT     -65535
   71: J        BININT     -65536
   76: J        BININT     2147483647
   81: J        BININT     -2147483647
   86: J        BININT     -2147483648
   91: (        MARK
   92: U            SHORT_BINSTRING 'abc'
   97: q            BINPUT     3
   99: h            BINGET     3
  101: (            MARK
  102: \x82             EXT1       240
  104: o                OBJ        (MARK at 101)
  105: q            BINPUT     4
  107: }            EMPTY_DICT
  108: q            BINPUT     5
  110: (            MARK
  111: U                SHORT_BINSTRING 'foo'
  116: q                BINPUT     6
  118: K                BININT1    1
  120: U                SHORT_BINSTRING 'bar'
  125: q                BINPUT     7
  127: K                BININT1    2
  129: u                SETITEMS   (MARK at 110)
  130: b            BUILD
  131: h            BINGET     4
  133: t            TUPLE      (MARK at 91)
  134: q        BINPUT     8
  136: h        BINGET     8
  138: K        BININT1    5
  140: e        APPENDS    (MARK at 5)
  141: .    STOP
highest protocol among opcodes = 2
"""

# set([1,2]) pickled from 2.x with protocol 2
DATA3 = b'\x80\x02\x82\t]q\x01(K\x01K\x02e\x85Rq\x02.'

# xrange(5) pickled from 2.x with protocol 2
DATA4 = b'\x80\x02\x82\x08K\x00K\x05K\x01\x87q\x00Rq\x01.'

# a SimpleCookie() object pickled from 2.x with protocol 2
DATA5 = (b'\x80\x02\x82\x0f)\x81q\x00U\x03key'
         b'q\x01\x82\x0e)\x81q\x02(U\x07commentq\x03U'
         b'\x00q\x04U\x06domainq\x05h\x04U\x06secureq\x06h\x04U\x07'
         b'expiresq\x07h\x04U\x07max-ageq\x08h\x04U\x07versionq\th\x04U'
         b'\x04pathq\nh\x04U\x08httponlyq\x0bh\x04u}q\x0c(U\x0b'
         b'coded_valueq\rU\x05valueq\x0eU\x05valueq\x0fh\x0eU\x03'
         b'keyq\x10h\x01ubs}q\x11b.')

# set([3]) pickled from 2.x with protocol 2
DATA6 = b'\x80\x02\x82\t]q\x00K\x03a\x85q\x01Rq\x02.'
DATA6_PYPY = b'\x80\x02\x82\tK\x03\x85q\x00\x85q\x01Rq\x02.'

def create_data():
    c = C()
    c.foo = 1
    c.bar = 2
    x = [0, 1, 2.0, 3.0+0j]
    # Append some integer test cases at cPickle.c's internal size
    # cutoffs.
    uint1max = 0xff
    uint2max = 0xffff
    int4max = 0x7fffffff
    x.extend([1, -1,
              uint1max, -uint1max, -uint1max-1,
              uint2max, -uint2max, -uint2max-1,
               int4max,  -int4max,  -int4max-1])
    y = ('abc', 'abc', c, c)
    x.append(y)
    x.append(y)
    x.append(5)
    return x

class AbstractPickleTests(unittest.TestCase):
    # Subclass must define self.dumps, self.loads.

    _testdata = create_data()

    def setUp(self):
        pass

    def test_misc(self):
        # test various datatypes not tested by testdata
        for proto in protocols:
            x = myint(4)
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

            x = (1, ())
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

            x = initarg(1, x)
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

        # XXX test __reduce__ protocol?

    def test_roundtrip_equality(self):
        expected = self._testdata
        for proto in protocols:
            s = self.dumps(expected, proto)
            got = self.loads(s)
            self.assertEqual(expected, got)

    def test_load_from_data2(self):
        self.assertEqual(self._testdata, self.loads(DATA2))

    def test_load_classic_instance(self):
        # See issue5180.  Test loading 2.x pickles that
        # contain an instance of old style class.
        for X, args in [(C, ()), (D, ('x',)), (E, ())]:
            xcode = copyreg._extension_registry[(X.__module__, X.__name__)]

            """
            0: \x80 PROTO      2
            2: (    MARK
            3: \x82     EXT1       X
            5: o        OBJ        (MARK at 2)
            6: q    BINPUT     0
            8: }    EMPTY_DICT
            9: q    BINPUT     1
            11: b    BUILD
            12: .    STOP
            """
            pickle2 = (b'\x80\x02(\x82'
                       b'X'
                       b'oq\x01}q\x02b.').replace(b'X', bytes([xcode]))
            self.assertEqual(X(*args), self.loads(pickle2))

    def test_recursive_list(self):
        l = []
        l.append(l)
        for proto in protocols:
            s = self.dumps(l, proto)
            x = self.loads(s)
            self.assertEqual(len(x), 1)
            self.assertTrue(x is x[0])

    def test_recursive_tuple(self):
        t = ([],)
        t[0].append(t)
        for proto in protocols:
            s = self.dumps(t, proto)
            x = self.loads(s)
            self.assertEqual(len(x), 1)
            self.assertEqual(len(x[0]), 1)
            self.assertTrue(x is x[0][0])

    def test_recursive_dict(self):
        d = {}
        d[1] = d
        for proto in protocols:
            s = self.dumps(d, proto)
            x = self.loads(s)
            self.assertEqual(list(x.keys()), [1])
            self.assertTrue(x[1] is x)

    def test_recursive_inst(self):
        i = C()
        i.attr = i
        for proto in protocols:
            s = self.dumps(i, proto)
            x = self.loads(s)
            self.assertEqual(dir(x), dir(i))
            self.assertIs(x.attr, x)

    def test_recursive_multi(self):
        l = []
        d = {1:l}
        i = C()
        i.attr = d
        l.append(i)
        for proto in protocols:
            s = self.dumps(l, proto)
            x = self.loads(s)
            self.assertEqual(len(x), 1)
            self.assertEqual(dir(x[0]), dir(i))
            self.assertEqual(list(x[0].attr.keys()), [1])
            self.assertTrue(x[0].attr[1] is x)

    def test_get(self):
        self.assertRaises(KeyError, self.loads, b'\x80\x02h\x00q\x00')

        self.assertEqual(self.loads(b'\x80\x02((Kdtq\x00h\x00l.))'),
                         [(100,), (100,)])
        # LONG_BINPUT and LONG_BINGET would normally only be used by the
        # pickle module if billions of objects had been memoized.
        self.assertEqual(self.loads(b'\x80\x02((Kdtr\x00\x00\x00\x00j\x00\x00\x00\x00l.))'),
                         [(100,), (100,)])

    def test_unicode(self):
        endcases = ['', '<\\u>', '<\\\u1234>', '<\n>',
                    '<\\>', '<\\\U00012345>',
                    # surrogates
                    '<\udc80>']
        for proto in protocols:
            for u in endcases:
                p = self.dumps(u, proto)
                u2 = self.loads(p)
                self.assertEqual(u2, u)

    def test_unicode_high_plane(self):
        t = '\U00012345'
        for proto in protocols:
            p = self.dumps(t, proto)
            t2 = self.loads(p)
            self.assertEqual(t2, t)

    def test_bytes(self):
        for proto in protocols:
            for s in b'', b'xyz', b'xyz'*100:
                p = self.dumps(s, proto)
                self.assertEqual(self.loads(p), s)
            for s in [bytes([i]) for i in range(256)]:
                p = self.dumps(s, proto)
                self.assertEqual(self.loads(p), s)
            for s in [bytes([i, i]) for i in range(256)]:
                p = self.dumps(s, proto)
                self.assertEqual(self.loads(p), s)

    def test_ints(self):
        import sys
        for proto in protocols:
            n = sys.maxsize
            while n:
                for expected in (-n, n):
                    s = self.dumps(expected, proto)
                    n2 = self.loads(s)
                    self.assertEqual(expected, n2)
                n = n >> 1

    def test_maxint64(self):
        maxint64 = (1 << 63) - 1
        data = b'I' + str(maxint64).encode("ascii") + b'\n.'
        got = self.loads(data)
        self.assertEqual(got, maxint64)

        # Try too with a bogus literal.
        data = b'I' + str(maxint64).encode("ascii") + b'JUNK\n.'
        self.assertRaises(ValueError, self.loads, data)

    def test_beyond_maxint64(self):
        beyond_maxint64 = -(1 << 64)
        data = b'I' + str(beyond_maxint64).encode("ascii") + b'\n.'
        self.assertRaises(ValueError, self.loads, data)

    def test_long(self):
        for proto in protocols:
            # 256 bytes is where LONG4 begins.
            for nbits in 1, 8, 8*254, 8*255, 8*256, 8*257:
                nbase = 1 << nbits
                for npos in nbase-1, nbase, nbase+1:
                    for n in npos, -npos:
                        pickle = self.dumps(n, proto)
                        got = self.loads(pickle)
                        self.assertEqual(n, got)
        # Try a monster.  This is quadratic-time in protos 0 & 1, so don't
        # bother with those.
        nbase = int("deadbeeffeedface", 16)
        nbase += nbase << 1000000
        for n in nbase, -nbase:
            p = self.dumps(n, 2)
            got = self.loads(p)
            self.assertEqual(n, got)

    def test_float(self):
        test_values = [0.0, 4.94e-324, 1e-310, 7e-308, 6.626e-34, 0.1, 0.5,
                       3.14, 263.44582062374053, 6.022e23, 1e30]
        test_values = test_values + [-x for x in test_values]
        for proto in protocols:
            for value in test_values:
                pickle = self.dumps(value, proto)
                got = self.loads(pickle)
                self.assertEqual(value, got)

    def test_reduce(self):
        pass

    def test_getinitargs(self):
        pass

    def test_pop_empty_stack(self):
        # Test issue7455
        s = b'0'
        self.assertRaises((pickle.UnpicklingError, IndexError), self.loads, s)

    def test_metaclass(self):
        a = use_metaclass()
        for proto in protocols:
            s = self.dumps(a, proto)
            b = self.loads(s)
            self.assertEqual(a.__class__, b.__class__)

    def test_dynamic_class(self):
        a = create_dynamic_class("my_dynamic_class", (object,))
        copyreg.pickle(pickling_metaclass, pickling_metaclass.__reduce__)
        for proto in protocols:
            s = self.dumps(a, proto)
            b = self.loads(s)
            self.assertEqual(a, b)

    def test_structseq(self):
        import time
        import os

        t = time.localtime()
        for proto in protocols:
            s = self.dumps(t, proto)
            u = self.loads(s)
            self.assertEqual(t, u)
            if hasattr(os, "stat"):
                t = os.stat(os.curdir)
                s = self.dumps(t, proto)
                u = self.loads(s)
                self.assertEqual(t, u)
            if hasattr(os, "statvfs"):
                t = os.statvfs(os.curdir)
                s = self.dumps(t, proto)
                u = self.loads(s)
                self.assertEqual(t, u)

    def test_ellipsis(self):
        for proto in protocols:
            s = self.dumps(..., proto)
            u = self.loads(s)
            self.assertEqual(..., u)

    def test_notimplemented(self):
        for proto in protocols:
            s = self.dumps(NotImplemented, proto)
            u = self.loads(s)
            self.assertEqual(NotImplemented, u)

    # Tests for protocol 2

    def test_proto(self):
        build_none = pickle.NONE + pickle.STOP
        for proto in protocols:
            expected = build_none
            if proto >= 2:
                expected = pickle.PROTO + bytes([proto]) + expected
            p = self.dumps(None, proto)
            self.assertEqual(p, expected)

        oob = protocols[-1] + 1     # a future protocol
        badpickle = pickle.PROTO + bytes([oob]) + build_none
        try:
            self.loads(badpickle)
        except ValueError as detail:
            self.assertTrue(str(detail).startswith(
                                            "unsupported pickle protocol"))
        else:
            self.fail("expected bad protocol number to raise ValueError")

    def test_long1(self):
        x = 12345678910111213141516178920
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)
            self.assertEqual(opcode_in_pickle(pickle.LONG1, s), proto >= 2)

    def test_long4(self):
        x = 12345678910111213141516178920 << (256*8)
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)
            self.assertEqual(opcode_in_pickle(pickle.LONG4, s), proto >= 2)

    def test_short_tuples(self):
        # Map (proto, len(tuple)) to expected opcode.
        expected_opcode = {(0, 0): pickle.TUPLE,
                           (0, 1): pickle.TUPLE,
                           (0, 2): pickle.TUPLE,
                           (0, 3): pickle.TUPLE,
                           (0, 4): pickle.TUPLE,

                           (1, 0): pickle.EMPTY_TUPLE,
                           (1, 1): pickle.TUPLE,
                           (1, 2): pickle.TUPLE,
                           (1, 3): pickle.TUPLE,
                           (1, 4): pickle.TUPLE,

                           (2, 0): pickle.EMPTY_TUPLE,
                           (2, 1): pickle.TUPLE1,
                           (2, 2): pickle.TUPLE2,
                           (2, 3): pickle.TUPLE3,
                           (2, 4): pickle.TUPLE,

                           (3, 0): pickle.EMPTY_TUPLE,
                           (3, 1): pickle.TUPLE1,
                           (3, 2): pickle.TUPLE2,
                           (3, 3): pickle.TUPLE3,
                           (3, 4): pickle.TUPLE,
                          }
        a = ()
        b = (1,)
        c = (1, 2)
        d = (1, 2, 3)
        e = (1, 2, 3, 4)
        for proto in protocols:
            for x in a, b, c, d, e:
                s = self.dumps(x, proto)
                y = self.loads(s)
                self.assertEqual(x, y, (proto, x, s, y))
                expected = expected_opcode[proto, len(x)]
                self.assertEqual(opcode_in_pickle(expected, s), True)

    def test_singletons(self):
        # Map (proto, singleton) to expected opcode.
        expected_opcode = {(0, None): pickle.NONE,
                           (1, None): pickle.NONE,
                           (2, None): pickle.NONE,
                           (3, None): pickle.NONE,

                           (0, True): pickle.INT,
                           (1, True): pickle.INT,
                           (2, True): pickle.NEWTRUE,
                           (3, True): pickle.NEWTRUE,

                           (0, False): pickle.INT,
                           (1, False): pickle.INT,
                           (2, False): pickle.NEWFALSE,
                           (3, False): pickle.NEWFALSE,
                          }
        for proto in protocols:
            for x in None, False, True:
                s = self.dumps(x, proto)
                y = self.loads(s)
                self.assertTrue(x is y, (proto, x, s, y))
                expected = expected_opcode[proto, x]
                self.assertEqual(opcode_in_pickle(expected, s), True)

    def test_newobj_tuple(self):
        x = MyTuple([1, 2, 3])
        x.foo = 42
        x.bar = "hello"
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(tuple(x), tuple(y))
            self.assertEqual(x.__dict__, y.__dict__)

    def test_newobj_list(self):
        x = MyList([1, 2, 3])
        x.foo = 42
        x.bar = "hello"
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(list(x), list(y))
            self.assertEqual(x.__dict__, y.__dict__)

    def test_newobj_generic(self):
        for proto in protocols:
            for C in myclasses:
                B = C.__base__
                x = C(C.sample)
                x.foo = 42
                s = self.dumps(x, proto)
                y = self.loads(s)
                detail = (proto, C, B, x, y, type(y))
                self.assertEqual(B(x), B(y), detail)
                self.assertEqual(x.__dict__, y.__dict__, detail)

    def test_newobj_proxies(self):
        # NEWOBJ should use the __class__ rather than the raw type
        classes = myclasses[:]
        # Cannot create weakproxies to these classes
        for c in (MyInt, MyTuple):
            classes.remove(c)
        for proto in protocols:
            for C in classes:
                B = C.__base__
                x = C(C.sample)
                x.foo = 42
                p = weakref.proxy(x)
                s = self.dumps(p, proto)
                y = self.loads(s)
                self.assertEqual(type(y), type(x))  # rather than type(p)
                detail = (proto, C, B, x, y, type(y))
                self.assertEqual(B(x), B(y), detail)
                self.assertEqual(x.__dict__, y.__dict__, detail)

    # Register a type with copyreg, with extension code extcode.  Pickle
    # an object of that type.  Check that the resulting pickle uses opcode
    # (EXT[124]) under proto 2..

    def produce_global_ext(self, extcode, opcode):
        e = ExtensionSaver(extcode)
        try:
            copyreg.add_extension(__name__, "SomeonesList", extcode)
            x = SomeonesList([1, 2, 3])
            x.foo = 42
            x.bar = "hello"

            # Dump using protocol 2 for test.
            s2 = self.dumps(x, 2)
            self.assertNotIn(__name__.encode("utf-8"), s2)
            self.assertNotIn(b"SomeonesList", s2)
            self.assertEqual(opcode_in_pickle(opcode, s2), True, repr(s2))

            y = self.loads(s2)
            self.assertEqual(list(x), list(y))
            self.assertEqual(x.__dict__, y.__dict__)

        finally:
            e.restore()

    def test_global_ext1(self):
        self.produce_global_ext(0x00000001, pickle.EXT1)  # smallest EXT1 code
        self.produce_global_ext(0x000000ff, pickle.EXT1)  # largest EXT1 code

    def test_global_ext2(self):
        self.produce_global_ext(0x00000100, pickle.EXT2)  # smallest EXT2 code
        self.produce_global_ext(0x0000ffff, pickle.EXT2)  # largest EXT2 code
        self.produce_global_ext(0x0000abcd, pickle.EXT2)  # check endianness

    def test_global_ext4(self):
        self.produce_global_ext(0x00010000, pickle.EXT4)  # smallest EXT4 code
        self.produce_global_ext(0x7fffffff, pickle.EXT4)  # largest EXT4 code
        self.produce_global_ext(0x12abcdef, pickle.EXT4)  # check endianness

    def test_negative_extension(self):
        self.assertRaises(pickle.UnpicklingError,
                          self.loads,
                          b'\x80\x02\x84\xff\xff\xff\xff.')

    def test_list_chunking(self):
        n = 10  # too small to chunk
        x = list(range(n))
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)
            num_appends = count_opcode(pickle.APPENDS, s)
            self.assertEqual(num_appends, proto > 0)

        n = 2500  # expect at least two chunks when proto > 0
        x = list(range(n))
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)
            num_appends = count_opcode(pickle.APPENDS, s)
            if proto == 0:
                self.assertEqual(num_appends, 0)
            else:
                self.assertTrue(num_appends >= 2)

    def test_dict_chunking(self):
        n = 10  # too small to chunk
        x = dict.fromkeys(range(n))
        for proto in protocols:
            s = self.dumps(x, proto)
            self.assertIsInstance(s, bytes_types)
            y = self.loads(s)
            self.assertEqual(x, y)
            num_setitems = count_opcode(pickle.SETITEMS, s)
            self.assertEqual(num_setitems, proto > 0)

        n = 2500  # expect at least two chunks when proto > 0
        x = dict.fromkeys(range(n))
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)
            num_setitems = count_opcode(pickle.SETITEMS, s)
            if proto == 0:
                self.assertEqual(num_setitems, 0)
            else:
                self.assertTrue(num_setitems >= 2)

    def test_simple_newobj(self):
        x = object.__new__(SimpleNewObj)  # avoid __init__
        x.abc = 666
        for proto in protocols:
            s = self.dumps(x, proto)
            self.assertEqual(opcode_in_pickle(pickle.NEWOBJ, s), proto >= 2)
            y = self.loads(s)   # will raise TypeError if __init__ called
            self.assertEqual(y.abc, 666)
            self.assertEqual(x.__dict__, y.__dict__)

    def test_newobj_list_slots(self):
        x = SlotList([1, 2, 3])
        x.foo = 42
        x.bar = "hello"
        s = self.dumps(x, 2)
        y = self.loads(s)
        self.assertEqual(list(x), list(y))
        self.assertEqual(x.__dict__, y.__dict__)
        self.assertEqual(x.foo, y.foo)
        self.assertEqual(x.bar, y.bar)

    def test_reduce_overrides_default_reduce_ex(self):
        for proto in protocols:
            x = REX_one()
            self.assertEqual(x._reduce_called, 0)
            s = self.dumps(x, proto)
            self.assertEqual(x._reduce_called, 1)
            y = self.loads(s)
            self.assertEqual(y._reduce_called, 0)

    def test_reduce_ex_called(self):
        for proto in protocols:
            x = REX_two()
            self.assertEqual(x._proto, None)
            s = self.dumps(x, proto)
            self.assertEqual(x._proto, proto)
            y = self.loads(s)
            self.assertEqual(y._proto, None)

    def test_reduce_ex_overrides_reduce(self):
        for proto in protocols:
            x = REX_three()
            self.assertEqual(x._proto, None)
            s = self.dumps(x, proto)
            self.assertEqual(x._proto, proto)
            y = self.loads(s)
            self.assertEqual(y._proto, None)

    def test_reduce_ex_calls_base(self):
        for proto in protocols:
            x = REX_four()
            self.assertEqual(x._proto, None)
            s = self.dumps(x, proto)
            self.assertEqual(x._proto, proto)
            y = self.loads(s)
            self.assertEqual(y._proto, proto)

    def test_reduce_calls_base(self):
        for proto in protocols:
            x = REX_five()
            self.assertEqual(x._reduce_called, 0)
            s = self.dumps(x, proto)
            self.assertEqual(x._reduce_called, 1)
            y = self.loads(s)
            self.assertEqual(y._reduce_called, 1)

    @no_tracing
    def test_bad_getattr(self):
        x = BadGetattr()
        for proto in protocols:
            self.assertRaises(RuntimeError, self.dumps, x, proto)

    def test_reduce_bad_iterator(self):
        # Issue4176: crash when 4th and 5th items of __reduce__()
        # are not iterators

        # Protocol 0 is less strict and also accept iterables.
        for proto in protocols:
            try:
                self.dumps(BadIteratorFourth(), proto)
            except (pickle.PickleError):
                pass
            try:
                self.dumps(BadIteratorFifth(), proto)
            except (pickle.PickleError):
                pass

    def test_many_puts_and_gets(self):
        # Test that internal data structures correctly deal with lots of
        # puts/gets.
        keys = ("aaa" + str(i) for i in range(300))
        large_dict = dict((k, [4, 5, 6]) for k in keys)
        obj = [dict(large_dict), dict(large_dict), dict(large_dict)]

        for proto in protocols:
            dumped = self.dumps(obj, proto)
            loaded = self.loads(dumped)
            self.assertEqual(loaded, obj,
                             "Failed protocol %d: %r != %r"
                             % (proto, obj, loaded))

    @unittest.skipIf(_is_pypy,
                     'PyPy does not guarantee the identity of strings. '
                     'See the discussion on '
                     'http://pypy.readthedocs.org/en/latest/cpython_differences.html#object-identity-of-primitive-values-is-and-id')
    def test_attribute_name_interning(self):
        # Test that attribute names of pickled objects are interned when
        # unpickling.
        for proto in protocols:
            x = C()
            x.foo = 42
            x.bar = "hello"
            s = self.dumps(x, proto)
            y = self.loads(s)
            x_keys = sorted(x.__dict__)
            y_keys = sorted(y.__dict__)
            for x_key, y_key in zip(x_keys, y_keys):
                self.assertIs(x_key, y_key)

    def test_unpickle_from_2x(self):
        # Unpickle non-trivial data from Python 2.x.
        loaded = self.loads(DATA3)
        self.assertEqual(loaded, set([1, 2]))
        loaded = self.loads(DATA4)
        self.assertEqual(type(loaded), type(range(0)))
        self.assertEqual(list(loaded), list(range(5)))
        loaded = self.loads(DATA5)
        self.assertEqual(type(loaded), SimpleCookie)
        self.assertEqual(list(loaded.keys()), ["key"])
        if _PY343:
            # The SimpleCookie object changed the way it gets
            # constructed in Python 3.4.3; the old behaviour was
            # broken.
            # See http://bugs.python.org/issue22775
            self.assertEqual(loaded["key"].value, "value")
        else:
            self.assertEqual(loaded["key"].value, "Set-Cookie: key=value")

    def test_pickle_to_2x(self):
        # Pickle non-trivial data with protocol 2, expecting that it yields
        # the same result as Python 2.x did.
        # NOTE: this test is a bit too strong since we can produce different
        # bytecode that 2.x will still understand.
        dumped = self.dumps(range(5), 2)
        self.assertEqual(dumped, DATA4)

        dumped = self.dumps(set([3]), 2)
        if not _is_pypy:
            # The integer in the set is pickled differently under PyPy
            # due to the differing identity semantics (?)
            self.assertEqual(dumped, DATA6)
        else:
            self.assertEqual(dumped, DATA6_PYPY)

    def test_large_pickles(self):
        # Test the correctness of internal buffering routines when handling
        # large data.
        for proto in protocols:
            data = (1, range, b'xy' * (30 * 1024), set)
            dumped = self.dumps(data, proto)
            loaded = self.loads(dumped)
            self.assertEqual(len(loaded), len(data))
            self.assertEqual(loaded, data)

    def test_empty_bytestring(self):
        # issue 11286
        empty = self.loads(b'\x80\x03U\x00q\x00.', encoding='koi8-r')
        self.assertEqual(empty, '')

    def test_int_pickling_efficiency(self):
        # Test compacity of int representation (see issue #12744)
        for proto in protocols:
            sizes = [len(self.dumps(2**n, proto)) for n in range(70)]
            # the size function is monotonic
            self.assertEqual(sorted(sizes), sizes)
            if proto >= 2:
                self.assertLessEqual(sizes[-1], 14)

    def check_negative_32b_binXXX(self, dumped):
        if sys.maxsize > 2**32:
            self.skipTest("test is only meaningful on 32-bit builds")
        # XXX Pure Python pickle reads lengths as signed and passes
        # them directly to read() (hence the EOFError)
        with self.assertRaises((pickle.UnpicklingError, EOFError,
                                ValueError, OverflowError)):
            self.loads(dumped)

    def test_negative_32b_binbytes(self):
        # On 32-bit builds, a BINBYTES of 2**31 or more is refused
        self.check_negative_32b_binXXX(b'\x80\x03B\xff\xff\xff\xffxyzq\x00.')

    def test_negative_32b_binunicode(self):
        # On 32-bit builds, a BINUNICODE of 2**31 or more is refused
        self.check_negative_32b_binXXX(b'\x80\x03X\xff\xff\xff\xffxyzq\x00.')

    def test_negative_32b_binput(self):
        # Issue #12847
        if sys.maxsize > 2**32:
            self.skipTest("test is only meaningful on 32-bit builds")
        dumped = b'\x80\x03X\x01\x00\x00\x00ar\xff\xff\xff\xff.'
        self.assertRaises(ValueError, self.loads, dumped)

    def _check_pickling_with_opcode(self, obj, opcode, proto):
        pickled = self.dumps(obj, proto)
        self.assertTrue(opcode_in_pickle(opcode, pickled))
        unpickled = self.loads(pickled)
        self.assertEqual(obj, unpickled)

    def test_appends_on_non_lists(self):
        # Issue #17720
        obj = REX_six([1, 2, 3])
        for proto in protocols:
            if proto == 0:
                self._check_pickling_with_opcode(obj, pickle.APPEND, proto)
            else:
                self._check_pickling_with_opcode(obj, pickle.APPENDS, proto)

    def test_setitems_on_non_dicts(self):
        obj = REX_seven({1: -1, 2: -2, 3: -3})
        for proto in protocols:
            if proto == 0:
                self._check_pickling_with_opcode(obj, pickle.SETITEM, proto)
            else:
                self._check_pickling_with_opcode(obj, pickle.SETITEMS, proto)

    def test_unsupported_protocols(self):
        for proto in unsupported_protocols:
            self.assertRaises(ValueError, self.dumps, 42, proto)

    def test_unsupported_opcodes(self):
        unsupported_opcodes = [
            pickle.DUP,
            pickle.FLOAT,
            pickle.LONG,
            pickle.PERSID,
            pickle.STRING,
            pickle.UNICODE,
            pickle.GET,
            pickle.PUT,
            pickle.FALSE,
            pickle.TRUE,
        ]
        for opcode in unsupported_opcodes:
            self.assertRaises(pickle.UnpicklingError, self.loads, opcode)

    def test_load_unregistered_extension(self):
        # >>> copy_reg.add_extension('__builtin__', 'set', 123456)
        # >>> pickle.dumps(set(), 2)
        pickled = b'\x80\x02\x84@\xe2\x01\x00]q\x00\x85q\x01Rq\x02.'
        self.assertRaises(ValueError, self.loads, pickled)

    def test_load_unregistered_global(self):
        self.assertRaises(pickle.UnpicklingError,
                          self.loads,
                          b'\x80\x02cos\nsystem\n(U\x10echo hello worldtR.')


class AbstractBytestrTests(unittest.TestCase):
    def unpickleEqual(self, data, unpickled):
        loaded = self.loads(data, encoding="bytes")
        self.assertEqual(loaded, unpickled)

    def test_load_str_protocol_2(self):
        """ Test str from protocol=2
        python 2: pickle.dumps('bytestring \x00\xa0', protocol=2) """
        self.unpickleEqual(
                b'\x80\x02U\rbytestring \x00\xa0q\x00.',
                b'bytestring \x00\xa0')

    def test_load_unicode_protocol_2(self):
        """ Test unicode with protocol=1
        python 2: pickle.dumps(u"\u041a\u043e\u043c\u043f\u044c\u044e\u0442\u0435\u0440", protocol=2) """
        self.unpickleEqual(
                b'\x80\x02X\x12\x00\x00\x00\xd0\x9a\xd0\xbe\xd0\xbc\xd0\xbf\xd1\x8c\xd1\x8e\xd1\x82\xd0\xb5\xd1\x80q\x00.',
                '\u041a\u043e\u043c\u043f\u044c\u044e\u0442\u0435\u0440')

class AbstractBytesFallbackTests(unittest.TestCase):
    def unpickleEqual(self, data, unpickled):
        loaded = self.loads(data, errors="bytes")
        self.assertEqual(loaded, unpickled)

    def test_load_instance(self):
        r"""Test instance pickle.

        Python 2: pickle.dumps({'x': 'ascii', 'y': '\xff'}) """
        self.unpickleEqual(
                b'\x80\x02}q\x00(U\x01yq\x01U\x01\xffq\x02U\x01xq\x03'
                b'U\x05asciiq\x04u.',
                {'x': 'ascii', 'y': b'\xff'})


class BigmemPickleTests(unittest.TestCase):

    # Binary protocols can serialize longs of up to 2GB-1

    @bigmemtest(size=_2G, memuse=1 + 1, dry_run=False)
    def test_huge_long_32b(self, size):
        data = 1 << (8 * size)
        try:
            for proto in protocols:
                if proto < 2:
                    continue
                with self.assertRaises((ValueError, OverflowError)):
                    self.dumps(data, protocol=proto)
        finally:
            data = None

    # Protocol 3 can serialize up to 4GB-1 as a bytes object
    # (older protocols don't have a dedicated opcode for bytes and are
    # too inefficient)

    @bigmemtest(size=_2G, memuse=1 + 1, dry_run=False)
    def test_huge_bytes_32b(self, size):
        data = b"abcd" * (size // 4)
        try:
            for proto in protocols:
                if proto < 3:
                    continue
                try:
                    pickled = self.dumps(data, protocol=proto)
                    self.assertTrue(b"abcd" in pickled[:15])
                    self.assertTrue(b"abcd" in pickled[-15:])
                finally:
                    pickled = None
        finally:
            data = None

    @bigmemtest(size=_4G, memuse=1 + 1, dry_run=False)
    def test_huge_bytes_64b(self, size):
        data = b"a" * size
        try:
            for proto in protocols:
                if proto < 3:
                    continue
                with self.assertRaises((ValueError, OverflowError)):
                    self.dumps(data, protocol=proto)
        finally:
            data = None

    # All protocols use 1-byte per printable ASCII character; we add another
    # byte because the encoded form has to be copied into the internal buffer.

    @bigmemtest(size=_2G, memuse=2 + ascii_char_size, dry_run=False)
    def test_huge_str_32b(self, size):
        data = "abcd" * (size // 4)
        try:
            for proto in protocols:
                try:
                    pickled = self.dumps(data, protocol=proto)
                    self.assertTrue(b"abcd" in pickled[:15])
                    self.assertTrue(b"abcd" in pickled[-15:])
                finally:
                    pickled = None
        finally:
            data = None

    # BINUNICODE (protocols 1, 2 and 3) cannot carry more than
    # 2**32 - 1 bytes of utf-8 encoded unicode.

    @bigmemtest(size=_4G, memuse=1 + ascii_char_size, dry_run=False)
    def test_huge_str_64b(self, size):
        data = "a" * size
        try:
            for proto in protocols:
                if proto == 0:
                    continue
                with self.assertRaises((ValueError, OverflowError)):
                    self.dumps(data, protocol=proto)
        finally:
            data = None


# Test classes for reduce_ex

class REX_one(object):
    """No __reduce_ex__ here, but inheriting it from object"""
    _reduce_called = 0
    def __reduce__(self):
        self._reduce_called = 1
        return REX_one, ()

copyreg.add_extension(__name__, "REX_one", next(extension_codes))

class REX_two(object):
    """No __reduce__ here, but inheriting it from object"""
    _proto = None
    def __reduce_ex__(self, proto):
        self._proto = proto
        return REX_two, ()

copyreg.add_extension(__name__, "REX_two", next(extension_codes))

class REX_three(object):
    _proto = None
    def __reduce_ex__(self, proto):
        self._proto = proto
        return REX_two, ()
    def __reduce__(self):
        raise TestFailed("This __reduce__ shouldn't be called")

copyreg.add_extension(__name__, "REX_three", next(extension_codes))

class REX_four(object):
    """Calling base class method should succeed"""
    _proto = None
    def __reduce_ex__(self, proto):
        self._proto = proto
        return object.__reduce_ex__(self, proto)

copyreg.add_extension(__name__, "REX_four", next(extension_codes))

class REX_five(object):
    """This one used to fail with infinite recursion"""
    _reduce_called = 0
    def __reduce__(self):
        self._reduce_called = 1
        return object.__reduce__(self)

copyreg.add_extension(__name__, "REX_five", next(extension_codes))

class REX_six(object):
    """This class is used to check the 4th argument (list iterator) of the reduce
    protocol.
    """
    def __init__(self, items=None):
        self.items = items if items is not None else []
    def __eq__(self, other):
        return type(self) is type(other) and self.items == self.items
    def append(self, item):
        self.items.append(item)
    def __reduce__(self):
        return type(self), (), None, iter(self.items), None

copyreg.add_extension(__name__, "REX_six", next(extension_codes))

class REX_seven(object):
    """This class is used to check the 5th argument (dict iterator) of the reduce
    protocol.
    """
    def __init__(self, table=None):
        self.table = table if table is not None else {}
    def __eq__(self, other):
        return type(self) is type(other) and self.table == self.table
    def __setitem__(self, key, value):
        self.table[key] = value
    def __reduce__(self):
        return type(self), (), None, None, iter(self.table.items())

copyreg.add_extension(__name__, "REX_seven", next(extension_codes))


class BadIteratorFourth(object):
    def __reduce__(self):
        # 4th item is not an iterator
        return list, (), None, [], None
copyreg.add_extension(__name__, "BadIteratorFourth", next(extension_codes))

class BadIteratorFifth(object):
    def __reduce__(self):
        # 5th item is not an iterator
        return dict, (), None, None, []
copyreg.add_extension(__name__, "BadIteratorFifth", next(extension_codes))

# Test classes for newobj

class MyInt(int):
    sample = 1

class MyFloat(float):
    sample = 1.0

class MyComplex(complex):
    sample = 1.0 + 0.0j

class MyStr(str):
    sample = "hello"

class MyUnicode(str):
    sample = "hello \u1234"

class MyTuple(tuple):
    sample = (1, 2, 3)

class MyList(list):
    sample = [1, 2, 3]

class MyDict(dict):
    sample = {"a": 1, "b": 2}

myclasses = [MyInt, MyFloat,
             MyComplex,
             MyStr, MyUnicode,
             MyTuple, MyList, MyDict]

for cls in myclasses:
    copyreg.add_extension(__name__, cls.__name__, next(extension_codes))

# Don't add this to extension registry at module import time, it's added &
# removed during execution of AbstractPickleTests.produce_global_ext()
class SomeonesList(list):
    sample = [1, 2, 3]


class SlotList(MyList):
    __slots__ = ["foo"]

copyreg.add_extension(__name__, "SlotList", next(extension_codes))

class SimpleNewObj(object):
    def __init__(self, a, b, c):
        # raise an error, to make sure this isn't called
        raise TypeError("SimpleNewObj.__init__() didn't expect to get called")

copyreg.add_extension(__name__, "SimpleNewObj", next(extension_codes))

class BadGetattr:
    def __getattr__(self, key):
        self.foo

copyreg.add_extension(__name__, "BadGetattr", next(extension_codes))


class AbstractPickleModuleTests(unittest.TestCase):

    def test_dump_closed_file(self):
        import os
        f = open(TESTFN, "wb")
        try:
            f.close()
            self.assertRaises(ValueError, pickle.dump, 123, f)
        finally:
            os.remove(TESTFN)

    def test_load_closed_file(self):
        import os
        f = open(TESTFN, "wb")
        try:
            f.close()
            self.assertRaises(ValueError, pickle.dump, 123, f)
        finally:
            os.remove(TESTFN)

    def test_load_from_and_dump_to_file(self):
        stream = io.BytesIO()
        data = [123, {}, 124]
        pickle.dump(data, stream)
        stream.seek(0)
        unpickled = pickle.load(stream)
        self.assertEqual(unpickled, data)

    def test_highest_protocol(self):
        # Of course this needs to be changed when HIGHEST_PROTOCOL changes.
        self.assertEqual(pickle.HIGHEST_PROTOCOL, 3)

    def test_callapi(self):
        f = io.BytesIO()
        # With and without keyword arguments
        pickle.dump(123, f, -1)
        pickle.dump(123, file=f, protocol=-1)
        pickle.dumps(123, -1)
        pickle.dumps(123, protocol=-1)
        pickle.Pickler(f, -1)
        pickle.Pickler(f, protocol=-1)

    def test_bad_init(self):
        # Test issue3664 (pickle can segfault from a badly initialized Pickler).
        # Override initialization without calling __init__() of the superclass.
        class BadPickler(pickle.Pickler):
            def __init__(self): pass

        class BadUnpickler(pickle.Unpickler):
            def __init__(self): pass

        self.assertRaises(pickle.PicklingError, BadPickler().dump, 0)
        self.assertRaises(pickle.UnpicklingError, BadUnpickler().load)

    def test_bad_input(self):
        # Test issue4298
        s = bytes([0x58, 0, 0, 0, 0x54])
        self.assertRaises(EOFError, pickle.loads, s)


class AbstractPersistentPicklerTests(unittest.TestCase):

    # This class defines persistent_id() and persistent_load()
    # functions that should be used by the pickler.  All even integers
    # are pickled using persistent ids.

    def persistent_id(self, object):
        if isinstance(object, int) and object % 2 == 0:
            self.id_count += 1
            return str(object)
        else:
            return None

    def persistent_load(self, oid):
        self.load_count += 1
        object = int(oid)
        assert object % 2 == 0
        return object

    def test_persistence(self):
        self.id_count = 0
        self.load_count = 0
        L = list(range(10))
        self.assertEqual(self.loads(self.dumps(L)), L)
        self.assertEqual(self.id_count, 5)
        self.assertEqual(self.load_count, 5)

    def test_bin_persistence(self):
        self.id_count = 0
        self.load_count = 0
        L = list(range(10))
        self.assertEqual(self.loads(self.dumps(L, 2)), L)
        self.assertEqual(self.id_count, 5)
        self.assertEqual(self.load_count, 5)


class AbstractPicklerUnpicklerObjectTests(unittest.TestCase):

    pickler_class = None
    unpickler_class = None

    def setUp(self):
        assert self.pickler_class
        assert self.unpickler_class

    def test_clear_pickler_memo(self):
        # To test whether clear_memo() has any effect, we pickle an object,
        # then pickle it again without clearing the memo; the two serialized
        # forms should be different. If we clear_memo() and then pickle the
        # object again, the third serialized form should be identical to the
        # first one we obtained.
        data = ["abcdefg", "abcdefg", 44]
        f = io.BytesIO()
        pickler = self.pickler_class(f)

        pickler.dump(data)
        first_pickled = f.getvalue()

        # Reset StringIO object.
        f.seek(0)
        f.truncate()

        pickler.dump(data)
        second_pickled = f.getvalue()

        # Reset the Pickler and StringIO objects.
        pickler.clear_memo()
        f.seek(0)
        f.truncate()

        pickler.dump(data)
        third_pickled = f.getvalue()

        self.assertNotEqual(first_pickled, second_pickled)
        self.assertEqual(first_pickled, third_pickled)

    def test_priming_pickler_memo(self):
        # Verify that we can set the Pickler's memo attribute.
        data = ["abcdefg", "abcdefg", 44]
        f = io.BytesIO()
        pickler = self.pickler_class(f)

        pickler.dump(data)
        first_pickled = f.getvalue()

        f = io.BytesIO()
        primed = self.pickler_class(f)
        primed.memo = pickler.memo

        primed.dump(data)
        primed_pickled = f.getvalue()

        self.assertNotEqual(first_pickled, primed_pickled)

    def test_priming_unpickler_memo(self):
        # Verify that we can set the Unpickler's memo attribute.
        data = ["abcdefg", "abcdefg", 44]
        f = io.BytesIO()
        pickler = self.pickler_class(f)

        pickler.dump(data)
        first_pickled = f.getvalue()

        f = io.BytesIO()
        primed = self.pickler_class(f)
        primed.memo = pickler.memo

        primed.dump(data)
        primed_pickled = f.getvalue()

        unpickler = self.unpickler_class(io.BytesIO(first_pickled))
        unpickled_data1 = unpickler.load()

        self.assertEqual(unpickled_data1, data)

        primed = self.unpickler_class(io.BytesIO(primed_pickled))
        primed.memo = unpickler.memo
        unpickled_data2 = primed.load()

        primed.memo.clear()

        self.assertEqual(unpickled_data2, data)
        self.assertTrue(unpickled_data2 is unpickled_data1)

    def test_reusing_unpickler_objects(self):
        data1 = ["abcdefg", "abcdefg", 44]
        f = io.BytesIO()
        pickler = self.pickler_class(f)
        pickler.dump(data1)
        pickled1 = f.getvalue()

        data2 = ["abcdefg", 44, 44]
        f = io.BytesIO()
        pickler = self.pickler_class(f)
        pickler.dump(data2)
        pickled2 = f.getvalue()

        f = io.BytesIO()
        f.write(pickled1)
        f.seek(0)
        unpickler = self.unpickler_class(f)
        self.assertEqual(unpickler.load(), data1)

        f.seek(0)
        f.truncate()
        f.write(pickled2)
        f.seek(0)
        self.assertEqual(unpickler.load(), data2)

    def _check_multiple_unpicklings(self, ioclass):
        for proto in protocols:
            data1 = [(x, str(x)) for x in range(2000)] + [b"abcde", set]
            f = ioclass()
            pickler = self.pickler_class(f, protocol=proto)
            pickler.dump(data1)
            pickled = f.getvalue()

            N = 5
            f = ioclass(pickled * N)
            unpickler = self.unpickler_class(f)
            for i in range(N):
                if f.seekable():
                    pos = f.tell()
                self.assertEqual(unpickler.load(), data1)
                if f.seekable():
                    self.assertEqual(f.tell(), pos + len(pickled))
            self.assertRaises(EOFError, unpickler.load)

    def test_multiple_unpicklings_seekable(self):
        self._check_multiple_unpicklings(io.BytesIO)

    def test_multiple_unpicklings_unseekable(self):
        self._check_multiple_unpicklings(UnseekableIO)

    def test_unpickling_buffering_readline(self):
        # Issue #12687: the unpickler's buffering logic could fail with
        # text mode opcodes.
        data = list(range(10))
        for proto in protocols:
            for buf_size in range(1, 11):
                f = io.BufferedRandom(io.BytesIO(), buffer_size=buf_size)
                pickler = self.pickler_class(f, protocol=proto)
                pickler.dump(data)
                f.seek(0)
                unpickler = self.unpickler_class(f)
                self.assertEqual(unpickler.load(), data)

    def test_noload_object(self):
        global _NOLOAD_OBJECT
        after = {}
        _NOLOAD_OBJECT = object()
        aaa = AAA()
        bbb = BBB()
        ccc = 1
        ddd = 1.0
        eee = ('eee', 1)
        fff = ['fff']
        ggg = {'ggg': 0}
        unpickler = self.unpickler_class
        f = io.BytesIO()
        pickler = self.pickler_class(f, protocol=2)
        pickler.dump(_NOLOAD_OBJECT)
        after['_NOLOAD_OBJECT'] = f.tell()
        pickler.dump(aaa)
        after['aaa'] = f.tell()
        pickler.dump(bbb)
        after['bbb'] = f.tell()
        pickler.dump(ccc)
        after['ccc'] = f.tell()
        pickler.dump(ddd)
        after['ddd'] = f.tell()
        pickler.dump(eee)
        after['eee'] = f.tell()
        pickler.dump(fff)
        after['fff'] = f.tell()
        pickler.dump(ggg)
        after['ggg'] = f.tell()
        f.seek(0)
        unpickler = self.unpickler_class(f)
        unpickler.noload() # read past _NOLOAD_OBJECT
        self.assertEqual(f.tell(), after['_NOLOAD_OBJECT'])

        noload = unpickler.noload() # read past aaa
        self.assertEqual(noload, None)
        self.assertEqual(f.tell(), after['aaa'])

        unpickler.noload() # read past bbb
        self.assertEqual(f.tell(), after['bbb'])

        noload = unpickler.noload() # read past ccc
        self.assertEqual(noload, ccc)
        self.assertEqual(f.tell(), after['ccc'])

        noload = unpickler.noload() # read past ddd
        self.assertEqual(noload, ddd)
        self.assertEqual(f.tell(), after['ddd'])

        noload = unpickler.noload() # read past eee
        self.assertEqual(noload, eee)
        self.assertEqual(f.tell(), after['eee'])

        noload = unpickler.noload() # read past fff
        self.assertEqual(noload, fff)
        self.assertEqual(f.tell(), after['fff'])

        noload = unpickler.noload() # read past ggg
        self.assertEqual(noload, ggg)
        self.assertEqual(f.tell(), after['ggg'])

    def test_functional_noload_dict_subclass(self):
        """noload() doesn't break or produce any output given a dict subclass"""
        # See http://bugs.python.org/issue1101399
        o = MyDict()
        o['x'] = 1
        f = io.BytesIO()
        pickler = self.pickler_class(f, protocol=2)
        pickler.dump(o)
        f.seek(0)
        unpickler = self.unpickler_class(f)
        noload = unpickler.noload()
        self.assertEqual(noload, None)


    def test_functional_noload_list_subclass(self):
        """noload() doesn't break or produce any output given a list subclass"""
        # See http://bugs.python.org/issue1101399
        o = MyList()
        o.append(1)
        f = io.BytesIO()
        pickler = self.pickler_class(f, protocol=2)
        pickler.dump(o)
        f.seek(0)
        unpickler = self.unpickler_class(f)
        noload = unpickler.noload()
        self.assertEqual(noload, None)

    def test_functional_noload_dict(self):
        """noload() implements the Python 2.6 behaviour and fills in dicts"""
        # See http://bugs.python.org/issue1101399
        o = dict()
        o['x'] = 1
        f = io.BytesIO()
        pickler = self.pickler_class(f, protocol=2)
        pickler.dump(o)
        f.seek(0)
        unpickler = self.unpickler_class(f)
        noload = unpickler.noload()
        self.assertEqual(noload, o)


    def test_functional_noload_list(self):
        """noload() implements the Python 2.6 behaviour and fills in lists"""
        # See http://bugs.python.org/issue1101399
        o = list()
        o.append(1)
        f = io.BytesIO()
        pickler = self.pickler_class(f, protocol=2)
        pickler.dump(o)
        f.seek(0)
        unpickler = self.unpickler_class(f)
        noload = unpickler.noload()
        self.assertEqual(noload, o)

    def test_noload_unregistered_global(self):
        f = io.BytesIO(b'\x80\x02cos\nsystem\n(U\x10echo hello worldtR.')
        unpickler = self.unpickler_class(f)
        self.assertRaises(pickle.UnpicklingError, unpickler.noload)


# Tests for dispatch_table attribute

REDUCE_A = 'reduce_A'

class AAA(object):
    def __reduce__(self):
        return str, (REDUCE_A,)

copyreg.add_extension(__name__, "AAA", next(extension_codes))

class BBB(object):
    pass

copyreg.add_extension(__name__, "BBB", next(extension_codes))

class AbstractDispatchTableTests(unittest.TestCase):

    def test_default_dispatch_table(self):
        # No dispatch_table attribute by default
        f = io.BytesIO()
        p = self.pickler_class(f, 2)
        with self.assertRaises(AttributeError):
            p.dispatch_table
        self.assertFalse(hasattr(p, 'dispatch_table'))

    def test_class_dispatch_table(self):
        # A dispatch_table attribute can be specified class-wide
        dt = self.get_dispatch_table()

        class MyPickler(self.pickler_class):
            dispatch_table = dt

        def dumps(obj, protocol=None):
            f = io.BytesIO()
            p = MyPickler(f, protocol)
            self.assertEqual(p.dispatch_table, dt)
            p.dump(obj)
            return f.getvalue()

        self._test_dispatch_table(dumps, dt)

    def test_instance_dispatch_table(self):
        # A dispatch_table attribute can also be specified instance-wide
        dt = self.get_dispatch_table()

        def dumps(obj, protocol=None):
            f = io.BytesIO()
            p = self.pickler_class(f, protocol)
            p.dispatch_table = dt
            self.assertEqual(p.dispatch_table, dt)
            p.dump(obj)
            return f.getvalue()

        self._test_dispatch_table(dumps, dt)

    def _test_dispatch_table(self, dumps, dispatch_table):
        def custom_load_dump(obj):
            return pickle.loads(dumps(obj, 2))

        def default_load_dump(obj):
            return pickle.loads(pickle.dumps(obj, 2))

        # pickling complex numbers using protocol 0 relies on copyreg
        # so check pickling a complex number still works
        z = 1 + 2j
        self.assertEqual(custom_load_dump(z), z)
        self.assertEqual(default_load_dump(z), z)

        # modify pickling of complex
        REDUCE_1 = 'reduce_1'
        def reduce_1(obj):
            return str, (REDUCE_1,)
        dispatch_table[complex] = reduce_1
        self.assertEqual(custom_load_dump(z), REDUCE_1)
        self.assertEqual(default_load_dump(z), z)

        # check picklability of AAA and BBB
        a = AAA()
        b = BBB()
        self.assertEqual(custom_load_dump(a), REDUCE_A)
        self.assertIsInstance(custom_load_dump(b), BBB)
        self.assertEqual(default_load_dump(a), REDUCE_A)
        self.assertIsInstance(default_load_dump(b), BBB)

        # modify pickling of BBB
        dispatch_table[BBB] = reduce_1
        self.assertEqual(custom_load_dump(a), REDUCE_A)
        self.assertEqual(custom_load_dump(b), REDUCE_1)
        self.assertEqual(default_load_dump(a), REDUCE_A)
        self.assertIsInstance(default_load_dump(b), BBB)

        # revert pickling of BBB and modify pickling of AAA
        REDUCE_2 = 'reduce_2'
        def reduce_2(obj):
            return str, (REDUCE_2,)
        dispatch_table[AAA] = reduce_2
        del dispatch_table[BBB]
        self.assertEqual(custom_load_dump(a), REDUCE_2)
        self.assertIsInstance(custom_load_dump(b), BBB)
        self.assertEqual(default_load_dump(a), REDUCE_A)
        self.assertIsInstance(default_load_dump(b), BBB)


if __name__ == "__main__":
    # Print some stuff that can be used to rewrite DATA{0,1,2}
    from pickletools import dis
    x = create_data()
    for i in range(3):
        p = pickle.dumps(x, i)
        print("DATA{0} = (".format(i))
        for j in range(0, len(p), 20):
            b = bytes(p[j:j+20])
            print("    {0!r}".format(b))
        print(")")
        print()
        print("# Disassembly of DATA{0}".format(i))
        print("DATA{0}_DIS = \"\"\"\\".format(i))
        dis(p)
        print("\"\"\"")
        print()
