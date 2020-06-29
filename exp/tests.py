from components.tests import monitor_test

import unittest


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromModule(monitor_test)
    unittest.TextTestRunner(verbosity=2).run(suite)
