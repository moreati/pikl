``pikl`` README
===============

.. image:: https://travis-ci.org/moreati/pikl.svg?branch=master
        :target: https://travis-ci.org/moreati/pikl

.. image:: https://coveralls.io/repos/github/moreati/pikl/badge.svg
   :target: https://coveralls.io/github/moreati/pikl
   :alt: Coverage status

.. image:: https://img.shields.io/pypi/v/pikl.svg
        :target: https://pypi.python.org/pypi/pikl
        :alt: PyPI

.. image:: https://img.shields.io/pypi/pyversions/pikl.svg
        :target: https://pypi.python.org/pypi/pikl
        :alt: Python versions

This package is an attempt to create a rehabilitated pickle module:

- GLOBAL and INST opcodes have been removed. The copyreg extension registry is
  left as the only (opt-in) mechanism to dump or load custom classes.

- Protocol 0 and 1 support has been removed. Only binary pickles are accepted.

- Protocol 3 is the default protocol on both Python 2.x and Python 3.x

``pikl`` is derived from zodbpickle_, a uniform pickling interface for ZODB.

.. _zodbpickle: https://github.com/zopefoundation/zodbpickle

Caution
-------

``pikl`` is ultimately derived from Python's ``pickle`` module.
Although efforts have been made to remove identified security vulnerabilities,
it is almost certain that more vulneravilities remain.

The ``pickle`` module is not intended to be secure against erroneous or
maliciously constructed data. Never unpickle data received from an
untrusted or unauthenticated source as arbitrary code might be executed.

Also see https://docs.python.org/3.6/library/pickle.html

General Usage
-------------

To use ``pikl`` instead of Python's inbuilt ``pickle`` module, replace::

    import pickle

by::

    import pikl.pickle as pikl

This provides compatibility, but has the effect that you get the fast implementation
in Python 3, while Python 2 uses the slow version.

To get a more deterministic choice of the implementation, use one of::

    import pikl.fastpickle as pikl # always C
    import pikl.slowpickle as pikl # always Python

A bytestream produced by ``pickle`` can by loaded by ``pikl`` provided it
meets certain restrictions (e.g. protocol >= 2, no use of GLOBAL opcode)::

    $ python3
    >>> import pickle
    >>> s = pickle.dumps({'abc': 2})
    >>> from pikl import pickle as pikl
    >>> pikl.loads(s)
    {'abc': 2}

Loading an earlier protocol will raise ``UnpicklingError``::

    >>> s = pickle.dumps({'abc': 2}, protocol=0)
    >>> pikl.loads(s)
    Traceback (most recent call last):
    ...
    pikl.pickle_3.UnpicklingError: Only binary pickle protocols are supported

Loading an unregistered class or callable will raise ``UnpicklingError``::

    >>> s = pickle.dumps(complex(2, 1))
    >>> pikl.loads(s)
    Traceback (most recent call last):
    ...
    pikl.pickle_3.UnpicklingError: GLOBAL opcode is not supported

Extension Registry
------------------

To provide an opt-in mechanism for loading classes or callables ``pikl`` uses
the extension registry in the ``copyreg`` module::

    >>> import copyreg
    >>> copyreg.add_extension('builtins', 'complex', 240)
    >>> s = pickle.dumps(complex(2, 1))
    >>> pikl.loads(s)
    (2+1j)

Both the pickler and unpickler must agree on the same registry codes. A future
version of pikl will include a mechanism (e.g. defined profiles) to make this
assist.
