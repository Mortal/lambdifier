import unittest
from lambdifier import get_def_source


class TestLines(unittest.TestCase):
    def test_simple(self):
        def f():
            return 42

        self.assertEqual(get_def_source(f), 'def f():\n    return 42\n' )


if __name__ == '__main__':
    unittest.main()
