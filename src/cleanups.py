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
        return Cleanup(self.next_cleanup_id, func, args, kwargs)

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
        listeners.starting(cleanup)
        try:
            retval = cleanup.run()
        except:
            listeners.failed(cleanup, sys.exc_info())
        else:
            listeners.completed(cleanup, retval)

Cleanups.instance = Cleanups()

################################################################################

class Cleanup():

    def __init__(self, id, func, args, kwargs):
        self.id = id
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.name = None

    def run(self):
        return self.func(*self.args, **self.kwargs)

    def __str__(self):
        name = self.name
        if name is not None:
            return "%i: %s" % (self.id, name)
        else:
            return "%i" % self.id

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
        return self.dispatch_notifications(CleanupListener.starting, cleanup)

    def completed(self, cleanup, retval):
        return self.dispatch_notifications(CleanupListener.completed, cleanup,
            retval)

    def failed(self, cleanup, exc_info):
        return self.dispatch_notifications(CleanupListener.failed, cleanup,
            exc_info)

    def dispatch_notifications(self, func, *args):
        for listener in self.listeners:
            try:
                func(listener, self.cleanups, *args)
            except:
                traceback.print_exc()

################################################################################

add = Cleanups.instance.add
add_to_front = Cleanups.instance.add_to_front
remove = Cleanups.instance.remove
