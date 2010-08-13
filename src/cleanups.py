import atexit
import os
import shutil
import threading
import traceback
import sys

__all__ = (
    "Cleanup",
    "Cleanups",
    "CleanupListener",
    "DebugCleanupListener",
)

class Cleanups():

    global_listeners = []
    global_lock = threading.Lock()

    def __init__(self):
        self.cleanups = []
        self.listeners = []
        self.next_cleanup_id = 0
        self.lock = threading.Lock()
        atexit.register(self.run)

    def add(self, func, *args, **kwargs):
        with self.lock:
            cleanup = self._new_cleanup(func, args, kwargs)
            self.cleanups.append(cleanup) # append() is atomic so no need to acquire self.lock
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
        with self.lock:
            cleanups = self.cleanups
            self.cleanups = []
            listeners = tuple(self.listeners)

        with self.global_lock:
            global_listeners = tuple(self.global_listeners)

        listeners = listeners + global_listeners
        listeners = CleanupListenerNotifier(self, listeners)

        for cleanup in cleanups:
            listeners.starting(cleanup)
            try:
                retval = cleanup.run()
            except:
                listeners.failed(self, cleanup, sys.exc_info())
            else:
                listeners.completed(cleanup, retval)

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

Cleanups.instance = Cleanups()

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

class CleanupListener():

    def starting(self, cleanups, cleanup):
        pass

    def completed(self, cleanups, cleanup, retval):
        pass

    def failed(self, cleanups, cleanup, exc_info):
        pass

class DebugCleanupListener(CleanupListener):

    def __init__(self, f=None):
        self.f = f if f is not None else sys.__stderr__

    def starting(self, cleanups, cleanup):
        self.log("Starting cleanup operation: %s" % cleanup)

    def completed(self, cleanups, cleanup, retval):
        self.log("Cleanup operation completed successfully: %s (returned %r)" % (cleanup, retval))

    def failed(self, cleanups, cleanup, exc_info):
        self.log("Cleanup operation FAILED: %s (%s)" % (cleanup, exc_info[1]))
        traceback.print_exception(*exc_info)

    def log(self, message):
        print(message, file=self.f)

class CleanupListenerNotifier():

    def __init__(self, cleanups, listeners):
        self.cleanups = cleanups
        self.listeners = listeners

    def starting(self, cleanup):
        return self.dispatch_notifications(CleanupListener.starting, cleanup)

    def completed(self, cleanup, retval):
        return self.dispatch_notifications(CleanupListener.completed, cleanup, retval)

    def failed(self, cleanup, exc_info):
        return self.dispatch_notifications(CleanupListener.failed, cleanup, exc_info)

    def dispatch_notifications(self, func, *args):
        for listener in self.listeners:
            try:
                func(listener, self.cleanups, *args)
            except:
                traceback.print_exc()

