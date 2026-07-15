"""
Tests for step6_report_generator.py
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from step6_report_generator import build_report, save_report


# ---------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------

@pytest.fixture
def minimal_data():
    """Minimal valid data for build_report."""
    from step3_anomaly_detection import Anomaly
    from step4_pattern_analysis import IncidentPattern

    entries = [
        {"timestamp": "2024-01-15 09:00:01", "level": "INFO",  "source": "app", "message": "started", "fields": {}},
        {"timestamp": "2024-01-15 09:20:01", "level": "ERROR", "source": "app", "message": "failed",  "fields": {}},
    ]

    anomalies = [
        Anomaly(
            anomaly_type="keyword",
            severity="CRITICAL",
            source="app",
            timestamp="2024-01-15 09:20:01",
            description="OOM kill detected",
            evidence=["Out of memory"],
        )
    ]

    patterns = [
        IncidentPattern(
            pattern_id="INC-001",
            pattern_name="Test pattern",
            severity="CRITICAL",
            start_time="2024-01-15 09:20:01",
            end_time="2024-01-15 09:20:01",
            sources=["app"],
            anomalies=anomalies,
            description="Test incident",
        )
    ]

    return entries, anomalies, patterns


# ---------------------------------------------------------------
# TESTS: build_report
# ---------------------------------------------------------------

class TestBuildReport:

    def test_returns_string(self, minimal_data):
        entries, anomalies, patterns = minimal_data
        result = build_report(entries, anomalies, patterns)
        assert isinstance(result, str)

    def test_contains_title(self, minimal_data):
        entries, anomalies, patterns = minimal_data
        result = build_report(entries, anomalies, patterns)
        assert "Incident Report" in result

    def test_contains_severity(self, minimal_data):
        entries, anomalies, patterns = minimal_data
        result = build_report(entries, anomalies, patterns)
        assert "CRITICAL" in result

    def test_contains_pattern_id(self, minimal_data):
        entries, anomalies, patterns = minimal_data
        result = build_report(entries, anomalies, patterns)
        assert "INC-001" in result

    def test_report_has_sections(self, minimal_data):
        """Report should have the main section headings."""
        entries, anomalies, patterns = minimal_data
        result = build_report(entries, anomalies, patterns)
        assert "Executive Summary" in result
        assert "Anomalies Detected" in result
        assert "Recommendations" in result

    def test_no_rca_includes_manual_analysis(self, minimal_data):
        """When rca_results=None the report should explain the cascade manually."""
        entries, anomalies, patterns = minimal_data
        result = build_report(entries, anomalies, patterns, rca_results=None)
        assert "Manual Analysis" in result or "rule-based" in result.lower() or "Root Cause" in result


# ---------------------------------------------------------------
# TESTS: save_report
# ---------------------------------------------------------------

class TestSaveReport:

    def test_file_is_created(self, tmp_path, monkeypatch):
        """save_report should write a file to the reports directory."""
        import step6_report_generator as rg

        # Point reports dir to tmp_path so we don't pollute the real folder
        monkeypatch.setattr(rg, "REPORTS_DIR", str(tmp_path))

        path = rg.save_report("# Test Report", filename="test_report.md")
        assert os.path.exists(path)

    def test_file_content_matches(self, tmp_path, monkeypatch):
        """The saved file should contain exactly what we passed in."""
        import step6_report_generator as rg
        monkeypatch.setattr(rg, "REPORTS_DIR", str(tmp_path))

        content = "# My Report\n\nSome content."
        path = rg.save_report(content, filename="check.md")

        with open(path) as f:
            saved = f.read()

        assert saved == content

    def test_auto_filename_contains_timestamp(self, tmp_path, monkeypatch):
        """When no filename given, the file name should have a timestamp in it."""
        import step6_report_generator as rg
        monkeypatch.setattr(rg, "REPORTS_DIR", str(tmp_path))

        path = rg.save_report("content")
        filename = os.path.basename(path)
        assert "incident_report_" in filename
        assert filename.endswith(".md")
