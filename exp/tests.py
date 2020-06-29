from components.tests import monitor_test
from components.tests import plots_test

import unittest


if __name__ == "__main__":
    suites = [
        unittest.TestLoader().loadTestsFromModule(monitor_test),
        unittest.TestLoader().loadTestsFromModule(plots_test)
    ]
    suite = unittest.TestSuite(suites)
    unittest.TextTestRunner(verbosity=2).run(suite)
