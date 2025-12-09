import unittest
import os
import shutil
import tempfile
from src.docx_formula_mover.scanner import DocxScanner, ScanResult
from src.docx_formula_mover import cli
from unittest.mock import patch, MagicMock

# We will run tests against the fixtures generated in d:/thinksolv/tast1_fr/fixtures
FIXTURES_DIR = "d:/thinksolv/tast1_fr/fixtures"

class TestDocxScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = DocxScanner()

    def test_has_display_math(self):
        # has_display_math.docx should correspond to formula_error
        # contains $$A=1$$
        res = self.scanner.scan_file(os.path.join(FIXTURES_DIR, "has_display_math.docx"))
        self.assertTrue(res.is_error)
        self.assertFalse(res.skipped)
        self.assertTrue(len(res.matches) >= 1)

    def test_escaped_dollar(self):
        # escaped_dollar.docx should correspond to no_error
        # contains \$ $100 -> unescaped $ but not $$
        # contains \$$ -> escaped $$
        res = self.scanner.scan_file(os.path.join(FIXTURES_DIR, "escaped_dollar.docx"))
        # We expect NO display math detected
        self.assertFalse(res.is_error)
        self.assertEqual(len(res.matches), 0)

    def test_inline_math_only(self):
        # inline_math_only.docx should correspond to no_error
        # contains $x+y$
        res = self.scanner.scan_file(os.path.join(FIXTURES_DIR, "inline_math_only.docx"))
        self.assertFalse(res.is_error)

    def test_split_runs_display(self):
        # split_runs_display.docx should correspond to formula_error
        # run1: $, run2: $ -> forms $$
        res = self.scanner.scan_file(os.path.join(FIXTURES_DIR, "split_runs_display.docx"))
        self.assertTrue(res.is_error)
        
    def test_no_math(self):
        res = self.scanner.scan_file(os.path.join(FIXTURES_DIR, "no_math.docx"))
        self.assertFalse(res.is_error)

    def test_not_docx(self):
        res = self.scanner.scan_file(os.path.join(FIXTURES_DIR, "not_a_docx.txt"))
        self.assertTrue(res.skipped)

class TestCLI(unittest.TestCase):
    def test_dry_run_scan(self):
        # Run CLI with dry-run on fixtures dir
        # We need to capture stdout or just verify no errors
        # Also verify reports are generated
        
        output_dir = os.path.join(FIXTURES_DIR, "output_report")
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
            
        # Construct args
        test_args = MagicMock()
        test_args.input_path = FIXTURES_DIR
        test_args.out = output_dir
        test_args.recursive = True
        test_args.dry_run = True
        test_args.verbose = False
        test_args.command = 'scan'
        
        cli.run_scan(test_args)
        
        self.assertTrue(os.path.exists(os.path.join(output_dir, "report.json")))
        self.assertTrue(os.path.exists(os.path.join(output_dir, "report.csv")))

if __name__ == '__main__':
    unittest.main()
