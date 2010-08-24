"""
test_cleanups.py
Unit tests for cleanups.py

Copyright (C) 2010  Denver Coneybeare

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import itertools
import threading
import unittest

import cleanups
from cleanups import Cleanup
from cleanups import Cleanups
from cleanups import CleanupListener

################################################################################

class CleanupsTestCase(unittest.TestCase):
    """
    Base class for all test cases for the "cleanups" library.
    """

    def func(self, name, retval=None, exception=None):
        """
        A convenience function that simply creates a new instance of
        `FunctionSimulator` with the given arguments.  The forcing of
        ``name`` as the first parameter makes it easier to locate which test
        failed based on the cleanup operation's name.
        """
        return FunctionSimulator(self, name=name, retval=retval,
            exception=exception)

################################################################################

class TestBasicFunctionality(CleanupsTestCase):
    """
    A small suite of tests that exercise the basic functionality of the cleanups
    API.  If any of these tests fail they should be treated as high priority
    because it means that that API is crippled in some way.
    """

    def test_run_one(self):
        func = self.func("Toronto")
        x = Cleanups()
        cleanup = x.add(func)
        self.assertIsInstance(cleanup, Cleanup)
        x.run()
        func.assertInvocation()

    def test_run_multiple(self):
        func1 = self.func("Kitchener")
        func2 = self.func("Waterloo")
        x = Cleanups()
        x.add(func1)
        x.add(func2)
        x.run()
        func1.assertInvocation()
        func2.assertInvocation()
        func2.assertInvokedBefore(func1)

    def test_remove_one(self):
        func = self.func("Cambridge")
        x = Cleanups()
        c1 = x.add(func)
        x.remove(c1)
        x.run()
        func.assertNotInvoked()

    def test_remove_multiple(self):
        func1 = self.func("Guelph")
        func2 = self.func("Hamilton")
        func3 = self.func("Brantford")
        x = Cleanups()
        c1 = x.add(func1)
        c2 = x.add(func2)
        x.add(func3)
        x.remove(c1)
        x.remove(c2)
        x.run()
        func1.assertNotInvoked()
        func2.assertNotInvoked()
        func3.assertInvoked()

    def test_args(self):
        func1 = self.func("Preston")
        func2 = self.func("Galt")
        func3 = self.func("Hespler")
        x = Cleanups()
        x.add(func1, 1, 2, "3")
        x.add(func2, key1="value1", key2=2)
        x.add(func3, 9, 8, "7", key6="six", key5=5)
        x.run()
        func1.assertInvocation(1, 2, "3")
        func2.assertInvocation(key1="value1", key2=2)
        func3.assertInvocation(9, 8, "7", key6="six", key5=5)

    def test_context_manager(self):
        func1 = self.func("London")
        func2 = self.func("Mississauga")
        with Cleanups() as x:
            x.add(func1)
            func1.assertNotInvoked()
            x.add(func2)
            func2.assertNotInvoked()
        func1.assertInvocation()
        func2.assertInvocation()

    def test_listener(self):
        func = self.func("Brampton")
        x = Cleanups()
        cleanup = x.add(func)
        listener = CleanupListenerHelper(self)
        x.add_listener(listener)
        x.run()
        func.assertInvoked()
        listener.starting.assertInvocation(listener, x, cleanup)
        listener.completed.assertInvocation(listener, x, cleanup, None)
        listener.failed.assertNotInvoked()
        listener.starting.assertInvokedBefore(func)
        func.assertInvokedBefore(listener.completed)

    def test_global_listener(self):
        func1 = self.func("Burlington")
        func2 = self.func("Stouffville")
        x1 = Cleanups()
        x2 = Cleanups()
        cleanup1 = x1.add(func1)
        cleanup2 = x1.add(func2)
        listener = CleanupListenerHelper(self)
        Cleanups.add_global_listener(listener)
        x1.run()
        x2.run()
        func1.assertInvoked()
        func2.assertInvoked()
        listener.starting.assertInvocationCount(2)
        listener.completed.assertInvocationCount(2)
        listener.failed.assertNotInvoked()

        listener.starting.invocations[0].assertInvokedBefore(func2.invocation)
        func2.invocation.assertInvokedBefore(listener.completed.invocations[0])
        listener.completed.invocations[0].assertInvokedBefore(
            listener.starting.invocations[1])
        listener.starting.invocations[1].assertInvokedBefore(func1.invocation)
        func1.invocation.assertInvokedBefore(listener.completed.invocations[1])

    def test_module_attributes(self):
        self.assertIsInstance(cleanups.cleanups, Cleanups)
        self.assertEqual(cleanups.add, cleanups.cleanups.add)
        self.assertEqual(cleanups.add_to_front, cleanups.cleanups.add_to_front)
        self.assertEqual(cleanups.remove, cleanups.cleanups.remove)

################################################################################

class TestCleanupListener(CleanupsTestCase):
    """
    Tests the CleanupListener class.  Since this class is just 3 empty methods,
    try and invoke those methods and ensure that they return None.
    """

    def test(self):
        x = CleanupListener()
        self.assertIsNone(x.starting(None, None))
        self.assertIsNone(x.completed(None, None, None))
        self.assertIsNone(x.failed(None, None, None))

if __name__ == "__main__":
    unittest.main()

################################################################################

class TestCleanup(CleanupsTestCase):
    """Tests the Cleanup class"""

    def test__init__(self):
        cleanups = Cleanups()
        id = 5
        retval = [1, 2, 3]
        func = FunctionSimulator(self, retval=retval, name="Vaughn")
        args = ["A", "b", "C"]
        kwargs = [("d", "D"), ("z", "A")]
        x = Cleanup(cleanups, id, func, args, kwargs)

        self.assertIs(x.cleanups, cleanups)
        self.assertEquals(x.id, id)
        self.assertIs(x.func, func)
        self.assertEquals(x.args, tuple(args))
        self.assertIsInstance(x.args, tuple)
        self.assertEquals(x.kwargs, dict(kwargs))
        self.assertIsInstance(x.kwargs, dict)
        self.assertIsNone(x.name)

        with self.assertRaises(TypeError):
            Cleanup(cleanups, id, func, 5, kwargs)
        with self.assertRaises(TypeError):
            Cleanup(cleanups, id, func, [], 5)

    def test__str__(self):
        x = Cleanup(None, 20, None, (), {})
        self.assertEqual(str(x), "20")
        x.name = "Scarborough"
        self.assertEqual(str(x), "20: Scarborough")
        x.id = 5
        self.assertEqual(str(x), "5: Scarborough")
        x.id = None
        self.assertEqual(str(x), "None: Scarborough")
        x.name = None
        self.assertEqual(str(x), "None")

    def test__call__(self):
        self.assertEqual(Cleanup.run, Cleanup.__call__)

    def test_run_normal(self):
        func = FunctionSimulator(self, retval=450, name="York")
        args = ()
        kwargs = {}
        x = Cleanup(None, 0, func, args, kwargs)
        actual_retval = x.run()
        func.assertInvocation()
        self.assertEqual(actual_retval, func.retval)

        actual_retval = x.run()
        func.assertInvocationCount(2)
        self.assertEqual(actual_retval, func.retval)

    def test_run_exception(self):
        exception = KeyError("message")
        func = FunctionSimulator(self, exception=exception, name="Etobicoke")
        args = ()
        kwargs = {}
        x = Cleanup(None, 0, func, args, kwargs)
        with self.assertRaises(type(func.exception)) as cm:
            x.run()
        self.assertIs(cm.exception, func.exception)

        with self.assertRaises(type(func.exception)) as cm:
            x.run()
        func.assertInvocationCount(2)
        self.assertIs(cm.exception, func.exception)

    def test_run_args(self):
        func = FunctionSimulator(self, name="Acton")
        args = (1, 2)
        kwargs = {"a": 1, "b": 2, "c": 3}
        x = Cleanup(None, 0, func, args, kwargs)
        x.run()
        func.assertInvocation(*args, **kwargs)
        x.run()
        func.assertInvocationCount(2)
        func.invocations[1].assertArgs(*args, **kwargs)

################################################################################

class FunctionInvocation():
    """
    Stores information about a method invocation.
    """

    def __init__(self, testcase, func, args, kwargs, retval, exception,
            seqnum, func_name):
        """
        Initializes a new instance of ``FunctionInvocation``.
        
        :Parameters:
            testcase : unittest.TestCase
                the case case to use when assertXXX() methods are to be invoked
            func : callable
                the function or method that was invoked
            args : list/tuple
                the positional arguments that were given to the function; will
                be converted to a tuple via ``tuple()``
            kwargs : dict
                the keyword arguments that were given to the function; will be
                converted to a new dict via ``dict()``
            retval :
                the value that was returned from the function; the meaning of
                this attribute if `exception` is not ``None`` is undefined
            exception :
                the exception that was raised by the function; ``None``
                indicates no exception was raised
            seqnum : int
                a sequence number that identifies the order in which this
                invocation occurred relative to other invocations
            func_name : string
                the name of the function to be used in messages
        """
        self.testcase = testcase
        self.func = func
        self.args = tuple(args)
        self.kwargs = dict(kwargs)
        self.retval = retval
        self.exception = exception
        self.seqnum = seqnum
        self.func_name = func_name

    def assertArgs(self, *args, **kwargs):
        """
        Asserts that `self.args` and `self.kwargs` are equal to the given
        positional arguments and keyword arguments.
        """
        actual_str = self.create_args_string(self.args, self.kwargs)
        expected_str = self.create_args_string(args, kwargs)
        message = "%s was invoked with arguments (%s), but expected (%s)" % (
            self.func_name, actual_str, expected_str)

        self.testcase.assertEqual(self.args, args, message)
        self.testcase.assertEqual(self.kwargs, kwargs, message)

    def assertInvokedBefore(self, other):
        """
        Asserts that this invocation occurred before another invocation.  The
        determination is done by comparing the sequence numbers, `seqnum`, of
        the two functions; the one with the lower value is considered to have
        been invoked before the other.
        
        :Parameters:
            other : `FunctionInvocation`
                the invocation to compare to this invocation for order
        """
        message = ("%s was invoked after %s, but expected the other way " +
            "around (%i>=%i)") % (self.func_name, other.func_name, self.seqnum,
            other.seqnum)
        self.testcase.assertLess(self.seqnum, other.seqnum, message)

    def get_args_string(self):
        """
        Shorthand for `create_args_string()` specified `self.args` and
        `self.kwargs` as arguments.
        """
        return self.create_args_string(self.args, self.kwargs)

    @staticmethod
    def create_args_string(args, kwargs):
        """
        Generates a string resembling a Python method call with the given
        arguments.

        :Parameters:
            args : tuple
                the positional arguments of the method call
            kwargs : dict
                the keyword arguments of the method call
        """
        args_strs = (repr(x) for x in args)
        kwargs_strs = ("%s=%r" % (x, kwargs[x]) for x in sorted(kwargs))
        s = ", ".join(itertools.chain(args_strs, kwargs_strs))
        return s

################################################################################

class FunctionSimulator():
    """
    A class that can be used directly as a function and records all of its
    invocations for later inspection.
    """

    COUNTER = itertools.count()
    """A counter shared by all instances of this class, used for global ordering
    of invocations; all access to this object should be done with the lock
    `LOCK` acquired in order to ensure thread safety."""

    COUNTER_LOCK = threading.Lock()
    """The lock to acquire prior to any access to `COUNTER`"""

    def __init__(self, testcase, retval=None, exception=None, name=None):
        """
        Initializes a new instance of ``FunctionSimulator``.
        
        :Parameters:
            testcase : unittest.TestCase
                the case case to use when assertXXX() methods are to be invoked
            retval :
                the value to return from `invoke()` (default: ``None``)
            exception :
                the exception to raise from `invoke()`; if ``None`` (the
                default) then do not raise any exceptions from ``invoke()``
            name : string
                a name to assign to this object; if ``None`` (the default) then
                a name will be created from the next sequence number returned
                from `next_seqnum()`
        """
        self.invocations = []
        self.invocation = None
        self.testcase = testcase
        self.retval = retval
        self.exception = exception

        if name is None:
            name = "%s_%04i" % (self.__class__.__name__, self.next_seqnum())
        self.name = name
        self.display_name = 'function "%s"' % name

    def reset(self):
        """
        Clears the list of recorded invocations.
        """
        self.invocations = []
        self.invocation = None

    def invoke(self, *args, **kwargs):
        """
        Records an invocation of this object.  All of the given arguments and
        a globally unique sequence number are stored in this object's invocation
        list.  The sequence numbers are always increasing and can be used to
        determine the total order of method invocations.
        """
        seqnum = self.next_seqnum()
        retval = self.retval
        exception = self.exception
        invocation = FunctionInvocation(self.testcase, self.invoke, args,
            kwargs, retval, exception, seqnum, self.display_name)
        self.invocations.append(invocation)
        self.invocation = invocation

        if exception is not None:
            raise exception

        return retval

    def assertInvoked(self):
        """
        Asserts that `invoke()` was invoked. 
        """
        message = 'function "%s" was not invoked' % self.name
        num_invocations = len(self.invocations)
        self.testcase.assertTrue(num_invocations > 0, message)

    def assertInvocationCount(self, expected):
        """
        Asserts that `invoke()` was invoked a specified number of times.
        
        :Parameters:
            expected : int
                the expected number of times for `invoke()` to have been invoked
        """
        actual = len(self.invocations)
        message = "%s was invoked %i times, but expected %i" % (
            self.display_name, actual, expected)
        self.testcase.assertEqual(actual, expected, message)

    def assertInvocation(self, *args, **kwargs):
        """
        Asserts that `invoke()` was invoked exactly once with the given
        arguments. 
        """
        self.assertInvocationCount(1)
        self.invocation.assertArgs(*args, **kwargs)

    def assertNotInvoked(self):
        """
        Asserts that `invoke()` was not invoked.  This method is similar
        functionally to invoking ``self.assertInvocationCount(0)`` but has a
        better error message in the case of failure.
        See `assertInvocationCount()`
        """
        num_invocations = len(self.invocations)
        if num_invocations > 0:
            invocations_str = "(%s)" % ", ".join(x.get_args_string() for x in
                self.invocations)
            message = ("%s was invoked %i times, but expected 0 invocations: %s"
                % (self.display_name, num_invocations, invocations_str))
            self.testcase.fail(message)

    def assertInvokedBefore(self, other):
        """
        Shorthand for 
        ``self.invocations[0].assertInvokedBefore(other.invocations[0])``.
        See `FunctionInvocation.assertInvokedBefore()`.  If one or both of this
        ``FunctionSimulator`` or ``other`` do not have exactly 1 invocation
        then AssertionError is raised. 
        
        :Parameters:
            other : `FunctionSimulator`
                the ``FunctionSimulator`` whose single invocation to ensure
                was invoked after this object's single invocation
        """
        assert self.invocation is not None
        assert other.invocation is not None
        self.invocation.assertInvokedBefore(other.invocation)

    @classmethod
    def next_seqnum(cls):
        """
        Generates and returns the next globally-unique sequence number.  This
        method is thread safe and may be invoked concurrently by multiple
        threads.
        """
        with cls.COUNTER_LOCK:
            return next(cls.COUNTER)

    __call__ = invoke

    def __str__(self):
        return str(self.display_name)

################################################################################

class CleanupListenerHelper():
    """
    An implementation of `CleanupListener` that records the invocation of the
    listener methods.
    """

    def __init__(self, testcase):
        self.starting = FunctionSimulator(testcase, name="starting")
        self.completed = FunctionSimulator(testcase, name="completed")
        self.failed = FunctionSimulator(testcase, name="failed")

################################################################################







