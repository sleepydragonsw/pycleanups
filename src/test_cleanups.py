import cleanups
import unittest

################################################################################

class CleanupsTestCase(unittest.TestCase):
    """
    Base class for all test cases for the "cleanups" library.
    """
    pass

################################################################################

class TestCleanupListener(CleanupsTestCase):
    """
    Tests the CleanupListener class.  Since this class is just 3 empty methods,
    try and invoke those methods and ensure that they return None.
    """

    def test(self):
        x = cleanups.CleanupListener()
        self.assertIsNone(x.starting(None, None))
        self.assertIsNone(x.completed(None, None, None))
        self.assertIsNone(x.failed(None, None, None))

if __name__ == "__main__":
    unittest.main()
