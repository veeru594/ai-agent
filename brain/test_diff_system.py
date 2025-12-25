import os
import unittest
from pathlib import Path
import tempfile
import shutil

# Mocking necessary parts
from brain.mcp_write import MCPWrite
from brain.diff_validator import DiffValidator, DiffValidationError

class MockContextEngine:
    def __init__(self, root, file_name):
        self.project_root = root
        self.focus_file = file_name
        self.file_index = [file_name]

    def has_loaded_file(self):
        return True

    def get_original_file(self):
        with open(os.path.join(self.project_root, self.focus_file), 'r', encoding='utf-8') as f:
             return f.read()

class TestDiffSystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file_name = "test_script.py"
        self.file_path = os.path.join(self.test_dir, self.test_file_name)
        
        # Create initial file
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("def hello():\n    print('Hello')\n    print('World')\n")

        self.context = MockContextEngine(self.test_dir, self.test_file_name)
        self.writer = MCPWrite(self.context)
        self.validator = DiffValidator()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_validator_rejects_non_diff(self):
        bad_diff = "def hello():\n    print('New World')"
        with self.assertRaises(DiffValidationError) as cm:
            self.validator.validate(bad_diff)
        self.assertIn("Not a unified diff", str(cm.exception))

    def test_validator_rejects_missing_headers(self):
        bad_diff = "--- a\n+++ b\n+ new line" # No @@
        with self.assertRaises(DiffValidationError):
            self.validator.validate(bad_diff)

    def test_validator_accepts_valid_diff(self):
        diff = """--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
 def hello():
-    print('Hello')
+    print('Hi')
     print('World')
"""
        try:
            self.validator.validate(diff)
        except DiffValidationError:
            self.fail("Validator rejected valid diff")

    def test_writer_applies_diff(self):
        diff = """--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
 def hello():
-    print('Hello')
+    print('Hi')
     print('World')
""" 
        self.writer.apply_diff(diff)
        
        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        expected = "def hello():\n    print('Hi')\n    print('World')\n"
        self.assertEqual(content, expected)

    def test_writer_catches_mismatch(self):
        # Diff expecting 'Unknown' instead of 'Hello'
        diff = """--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
 def hello():
-    print('Unknown')
+    print('Hi')
     print('World')
""" 
        try:
            self.writer.apply_diff(diff)
            self.fail("Should have failed due to context mismatch")
        except Exception as e:
            self.assertIn("Context mismatch", str(e))

if __name__ == '__main__':
    unittest.main()
