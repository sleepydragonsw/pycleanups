PyCleaups
By: Denver Coneybeare
August 24, 2010

================================================================================
1. INTRODUCTION
================================================================================

PyCleanups is a small library for the Python programming language that provides
the ability to register and execute cleanup operations.  In its essence it is an
extension to the "atexit" module by adding a more user-friendly interface and
more functionality.  The "atexit" modules allows registering functions to be
invoked when a Python application terminates... that's it.  The PyCleanups
library provides this as well, but also the ability to unregister cleanup
operation, execute cleanup operations at any time, and listen for events
pertaining to the execution of cleanup operations.

================================================================================
2. INSTALLATION
================================================================================

PyCleanups uses the standard distutils setup script which can be used to install
it.  Simply run the following command from a command line:

    python setup.py install

================================================================================
3. USAGE
================================================================================

To use the PyCleanups library include the following line prior to using any
of its classes or functions:

    import cleanups

To register a function "func" to be invoked when the Python interpreter
terminates (ie. the same thing as atexit.register()) do the following:

    cleanups.add(func)

You can also specify positional and keyword arguments for the method call.  For
example, to specify 1 and 2 as positional arguments and id=3 as the keyword
arguments do the following:

    cleanups.add(func, 1, 2, id=3)

The add() function returns a new cleanups.Cleanup object that uniquely
identifies the cleanup operation just registered.  To remove the cleanup so that
it will not be invoked simply hold a reference to the Cleanup object and ues the
cleanups.remove() method as below:

    cleanup = cleanups.add(func)
    cleanups.remove(cleanup)

The functions above are actually just aliases for the corresponding methods of
the cleanups.Cleanups class on a globally-shared instance.  To create a new
instance of cleanups.Cleanups to use create a new instance and add/remove
cleanup operations to/from it.  The cleanups can be executed by invoking the
run() method of the cleanups.Cleanups object:

    my_cleanups = cleanups.Cleanups()
    my_cleanups.add(func1)
    my_cleanups.add(func2)
    my_cleanups.run()

The cleanups.Cleanups object also implements the context management protocol
and the cleanup operations will be executed when the context is exited.  For
example, in the code below the cleanup operations will be executed when the
context management block is exited:

    with cleanups.Cleanups() as my_cleanups:
        my_cleanups.add(func1)
        my_cleanups.add(func2)

For additional functionality provided by the cleanups.Cleanups class, such as
adding listeners, see the source code.
