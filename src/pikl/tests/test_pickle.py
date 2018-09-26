import unittest

class TestImportability(unittest.TestCase):

    def test_Pickler(self):
        from pikl.pickle import Pickler

    def test_Unpickler(self):
        from pikl.pickle import Unpickler

    def test_load(self):
        from pikl.pickle import load

    def test_loads(self):
        from pikl.pickle import load

    def test_dump(self):
        from pikl.pickle import dumps

    def test_dumps(self):
        from pikl.pickle import dumps


def test_suite():
    import sys
    if sys.version_info[0] >= 3:
        from .test_pickle_3 import test_suite
    else:
        from .test_pickle_2 import test_suite
    from . import test_pickletools

    return unittest.TestSuite((
        test_suite(),
        test_pickletools.test_suite(),
        unittest.makeSuite(TestImportability),
    ))
