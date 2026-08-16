"""PaperHub 测试套件"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.utils import PaperResult, safe_filename, extract_doi, dedup_results, sort_results, filter_results, export_bibtex, export_csv


class TestPaperResult(unittest.TestCase):
    def test_basic(self):
        p = PaperResult(title="Test", doi="10.1234/test", year="2023", authors=["A"], platform="arxiv")
        self.assertEqual(p.title, "Test")
        self.assertEqual(p.doi, "10.1234/test")
        self.assertEqual(p.year, "2023")
        d = p.to_dict()
        self.assertIn("title", d)
        self.assertIn("doi", d)

    def test_empty(self):
        p = PaperResult()
        self.assertEqual(p.title, "")
        self.assertEqual(p.authors, [])
        self.assertEqual(p.to_dict(), {})


class TestSafeFilename(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(safe_filename("Hello World"), "Hello_World")
        self.assertEqual(safe_filename("a/b*c"), "a_b_c")

    def test_max_len(self):
        result = safe_filename("a" * 100, max_len=10)
        self.assertEqual(len(result), 10)


class TestExtractDOI(unittest.TestCase):
    def test_basic(self):
        doi = extract_doi("https://doi.org/10.1234/test.567")
        self.assertIsNotNone(doi)
        self.assertIn("10.1234", doi)

    def test_none(self):
        self.assertIsNone(extract_doi("no doi here"))


class TestDedup(unittest.TestCase):
    def test_doi_dedup(self):
        r1 = PaperResult(title="Paper A", doi="10.1234/a", authors=["X"], platform="arxiv")
        r2 = PaperResult(title="Paper A", doi="10.1234/a", authors=["X", "Y"], platform="crossref")
        result = dedup_results([r1, r2])
        self.assertEqual(len(result), 1)
        # 保留字段更丰富的
        self.assertEqual(len(result[0].authors), 2)

    def test_no_dup(self):
        r1 = PaperResult(title="Paper A", doi="10.1234/a")
        r2 = PaperResult(title="Paper B", doi="10.5678/b")
        result = dedup_results([r1, r2])
        self.assertEqual(len(result), 2)


class TestSort(unittest.TestCase):
    def test_by_year(self):
        r1 = PaperResult(title="Old", year="2020")
        r2 = PaperResult(title="New", year="2024")
        result = sort_results([r1, r2], by="year")
        self.assertEqual(result[0].year, "2024")
        self.assertEqual(result[1].year, "2020")


class TestFilter(unittest.TestCase):
    def test_year_range(self):
        r1 = PaperResult(title="A", year="2020")
        r2 = PaperResult(title="B", year="2022")
        r3 = PaperResult(title="C", year="2024")
        result = filter_results([r1, r2, r3], year_from="2022", year_to="2023")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].year, "2022")

    def test_author(self):
        r1 = PaperResult(title="A", authors=["Alice Smith"])
        r2 = PaperResult(title="B", authors=["Bob Jones"])
        result = filter_results([r1, r2], author="Alice")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "A")


class TestExport(unittest.TestCase):
    def setUp(self):
        self.papers = [
            PaperResult(title="Test Paper", doi="10.1234/test", year="2023", authors=["Alice"], source="Journal"),
        ]

    def test_bibtex(self):
        bib = export_bibtex(self.papers)
        self.assertIn("@article", bib)
        self.assertIn("Test Paper", bib)
        self.assertIn("10.1234/test", bib)

    def test_csv(self):
        csv = export_csv(self.papers)
        self.assertIn("Test Paper", csv)
        self.assertIn("10.1234/test", csv)


class TestPlatformDiscovery(unittest.TestCase):
    def test_discover(self):
        from main import discover_platforms
        platforms = discover_platforms()
        self.assertGreaterEqual(len(platforms), 10)
        self.assertIn("arxiv", platforms)
        self.assertIn("crossref", platforms)


if __name__ == "__main__":
    unittest.main(verbosity=2)