__all__ = (
    "Cleanup",
    "Cleanups",
    "CleanupListener",
    "DebugCleanupListener",
)

import atexit
import os
import shutil
import threading
import traceback
import sys

################################################################################

class Cleanups():

    global_listeners = []
    global_lock = threading.Lock()

    def __init__(self, atexit_register=True):
        self.cleanups = []
        self.listeners = []
        self.next_cleanup_id = 0
        self.lock = threading.Lock()

        if atexit_register:
            atexit.register(self.run)

    def add(self, func, *args, **kwargs):
        with self.lock:
            cleanup = self._new_cleanup(func, args, kwargs)
            self.cleanups.append(cleanup)
        return cleanup

    def add_to_front(self, func, *args, **kwargs):
        with self.lock:
            cleanup = self._new_cleanup(func, args, kwargs)
            self.cleanups.insert(0, cleanup)
        return cleanup

    def add_unlink(self, path):
        self.add(os.unlink, path)

    def add_rmtree(self, path):
        self.add(shutil.rmtree, path)

    def add_listener(self, listener):
        self.listeners.append(listener)

    def remove_listener(self, listener):
        self.listeners.remove(listener)

    @classmethod
    def add_global_listener(cls, listener):
        with cls.global_lock:
            cls.global_listeners.append(listener)

    @classmethod
    def remove_global_listener(cls, listener):
        with cls.global_lock:
            cls.global_listeners.remove(listener)

    def remove(self, cleanup):
        with self.lock:
            self.cleanups.remove(cleanup)

    def clear(self):
        with self.lock:
            self.cleanups.clear()

    def run(self):
        (cleanups, listeners) = self._get_cleanups_and_listeners_for_execution()
        cleanups.reverse()
        for cleanup in cleanups:
            self._execute_cleanup(cleanup, listeners)

    def __contains__(self, cleanup):
        with self.lock:
            return cleanup in self.cleanups

    def __len__(self):
        with self.lock:
            return len(self.cleanups)

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.run()

    def _new_cleanup(self, func, args, kwargs):
        # ASSERTION: thread must have acquired self.lock
        self.next_cleanup_id += 1
        return Cleanup(self, self.next_cleanup_id, func, args, kwargs)

    def _get_cleanups_and_listeners_for_execution(self):
        with self.lock:
            cleanups = self.cleanups
            self.cleanups = []
            listeners = tuple(self.listeners)

        with self.global_lock:
            global_listeners = tuple(self.global_listeners)

        listeners = global_listeners + listeners
        listeners = _CleanupListenerNotifier(self, listeners)

        return (cleanups, listeners)

    def _execute_cleanup(self, cleanup, listeners):
        if not listeners.starting(cleanup):
            try:
                retval = cleanup.run()
            except:
                listeners.failed(cleanup, sys.exc_info())
            else:
                listeners.completed(cleanup, retval)

################################################################################

class Cleanup():
    """
    Stores information about a cleanup operation.
    """

    def __init__(self, cleanups, id, func, args, kwargs):
        """
        Initializes a new instance of ``Cleanup``.
        
        :Parameters:
            cleanups : `Cleanups`
                the ``Cleanups`` object that is creating this object
            id : int
                the ID of this cleanup, as assigned by the `Cleanups` object
                creating it
            func : callable
                the function to execute
            args : iterable
                the positional arguments to specify when invoking ``func``;
                will be converted to a tuple using the ``tuple()`` function and
                the tuple will be stored in the attributes of this object
            kwargs : dict
                will be converted to a dict using the ``dict()`` function and
                the dict will be stored in the attributes of this object
        """

        self.cleanups = cleanups
        """The `Cleanups` object to which this object belongs."""

        self.id = id
        """An integer whose value is the ID of this cleanup; initialized to the
        value of the ``id`` parameter in `__init__()`"""

        self.func = func
        """A callable whose value is the function of this cleanup; initialized
        to the value of the ``func`` parameter in `__init__()`"""

        self.args = tuple(args)
        """A tuple whose value is the positional argument to specify to `func`;
        initialized to the value of the ``args`` parameter in `__init__()`"""

        self.kwargs = dict(kwargs)
        """A dict whose value is the keyword argument to specify to `func`;
        initialized to the value of the ``kwargs`` parameter in `__init__()`"""

        self.name = None
        """A string whose value is a name for this cleanup; initialized to
        ``None`` in `__init__()`; it may be assigned to another value after
        creation for debugging purposes"""

    def run(self):
        """
        Executes this cleanup.  Invokes `self.func` with positional arguments
        `self.args` and keyword arguments `self.kwargs`, returning whatever the
        function returns or raising whatever it raises.
        """
        return self.func(*self.args, **self.kwargs)

    def __str__(self):
        """
        Generates and returns a string representation of this object.  If
        `self.name` is not ``None`` then returns `self.id` followed by
        `self.name`; otherwise, just returns `self.id`
        """
        name = self.name
        if name is not None:
            return "%s: %s" % (self.id, name)
        else:
            return "%s" % self.id

    __call__ = run

################################################################################

class CleanupListener():
    """
    Listener that can be added to a `Cleanups` object to be notified of the
    execution of cleanups. The implementation of every method in this class does
    nothing, but subclasses may override these methods to respond to the events.
    
    Listeners are registered via the `Cleanups.add_listener()` and
    `Cleanups.add_global_listener()` methods.  They can be unregistered with the
    `Cleanups.remove_listener()` and `Cleanups.remove_global_listener()`
    methods.  The callbacks occur in the `Cleanups.run()` method.
    """

    def starting(self, cleanups, cleanup):
        """
        Invoked before a cleanup operation begins.
        See `Cleanups.run()` for details.
        If the return value evaluates to ``True`` then the cleanup will *not*
        be executed by the `Cleanups` calling this method, effectively skipping
        it.
        
        :Parameters:
            cleanups : `Cleanups`
                the `Cleanups` object that is executing the cleanup operation
            cleanup : `Cleanup`
                the `Cleanup` that is about to be executed
        """
        pass

    def completed(self, cleanups, cleanup, retval):
        """
        Invoked after a cleanup completes successfully.
        Only one of `completed()` or `failed()`, not both, is invoked for a
        given cleanup execution.
        See `Cleanups.run()` for details.
        
        :Parameters:
            cleanups : `Cleanups`
                the `Cleanups` object that executed the cleanup operation
            cleanup : `Cleanup`
                the `Cleanup` that was executed
            retval :
                the value that was returned from the cleanup's method
        """
        pass

    def failed(self, cleanups, cleanup, exc_info):
        """
        Invoked after a cleanup completes unsuccessfully by raising an
        exception.
        Only one of `completed()` or `failed()`, not both, is invoked for a
        given cleanup execution.
        See `Cleanups.run()` for details.
        
        :Parameters:
            cleanups : `Cleanups`
                the `Cleanups` object that executed the cleanup operation
            cleanup : `Cleanup`
                the `Cleanup` that was executed
            exc_info : tuple
                the tuple ``(type, value, traceback)`` as returned from
                ``sys.exc_info()`` about the exception that was raised by the
                cleanup; ensure to not retain references to this tuple or the
                ``traceback`` element after this method completes to avoid
                memory leaks
        """
        pass

################################################################################

class DebugCleanupListener(CleanupListener):

    def __init__(self, f=None):
        self.f = f if f is not None else sys.__stderr__

    def starting(self, cleanups, cleanup):
        self.log("Starting cleanup operation: %s" % cleanup)

    def completed(self, cleanups, cleanup, retval):
        self.log("Cleanup operation completed successfully: %s (returned %r)" %
            (cleanup, retval))

    def failed(self, cleanups, cleanup, exc_info):
        self.log("Cleanup operation FAILED: %s (%s)" % (cleanup, exc_info[1]))
        traceback.print_exception(*exc_info)

    def log(self, message):
        print(message, file=self.f)

################################################################################

class _CleanupListenerNotifier():

    def __init__(self, cleanups, listeners):
        self.cleanups = cleanups
        self.listeners = listeners

    def starting(self, cleanup):
        return self.dispatch_notifications(lambda x: x.starting, cleanup)

    def completed(self, cleanup, retval):
        return self.dispatch_notifications(lambda x: x.completed, cleanup,
            retval)

    def failed(self, cleanup, exc_info):
        return self.dispatch_notifications(lambda x: x.failed, cleanup,
            exc_info)

    def dispatch_notifications(self, get_func_from_listener, *args):
        result = False
        for listener in self.listeners:
            try:
                func = get_func_from_listener(listener)
                if func(listener, self.cleanups, *args):
                    result = True
            except:
                traceback.print_exc()
        return result

################################################################################

cleanups = Cleanups()
add = cleanups.add
add_to_front = cleanups.add_to_front
remove = cleanups.remove
