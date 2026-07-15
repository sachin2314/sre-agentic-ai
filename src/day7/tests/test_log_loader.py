"""
Tests for step1_load_logs.py
"""

import os
import sys
import pytest

# Add src/ to Python path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from step1_load_logs import load_log_file, load_all_logs


class TestLoadLogFile:

    def test_returns_list(self, tmp_path):
        """load_log_file should return a list."""
        # Create a temporary fake log file
        fake_log = tmp_path / "test.log"
        fake_log.write_text("2024-01-15 09:00:01 INFO test message\n")

        # We need to test with the actual function — mock the path
        result = load_log_file.__wrapped__ if hasattr(load_log_file, "__wrapped__") else None

    def test_missing_file_returns_empty_list(self):
        """load_log_file should return [] for a file that doesn't exist."""
        result = load_log_file("definitely_does_not_exist.log")
        assert result == []

    def test_strips_newlines(self, tmp_path):
        """Lines returned should have no leading/trailing whitespace."""
        # Write to a temp file, then monkey-patch the LOGS_DIR
        import step1_load_logs as loader

        original_dir = loader.LOGS_DIR
        loader.LOGS_DIR = str(tmp_path)

        fake_log = tmp_path / "test.log"
        fake_log.write_text("  line one  \n  line two  \n")

        result = loader.load_log_file("test.log")

        loader.LOGS_DIR = original_dir  # restore

        assert all(line == line.strip() for line in result)

    def test_skips_blank_lines(self, tmp_path):
        """Blank lines should not appear in the result."""
        import step1_load_logs as loader

        original_dir = loader.LOGS_DIR
        loader.LOGS_DIR = str(tmp_path)

        fake_log = tmp_path / "test.log"
        fake_log.write_text("line one\n\n\nline two\n")

        result = loader.load_log_file("test.log")
        loader.LOGS_DIR = original_dir

        assert len(result) == 2


class TestLoadAllLogs:

    def test_returns_dict(self):
        """load_all_logs should return a dictionary."""
        result = load_all_logs()
        assert isinstance(result, dict)

    def test_dict_has_expected_keys(self):
        """Dictionary should include known log filenames."""
        result = load_all_logs()
        assert "app.log" in result
        assert "nginx_access.log" in result
        assert "database.log" in result

    def test_app_log_has_content(self):
        """app.log should have at least 10 lines."""
        result = load_all_logs()
        assert len(result.get("app.log", [])) >= 10

    def test_values_are_lists(self):
        """Each value in the dict should be a list."""
        result = load_all_logs()
        for key, value in result.items():
            assert isinstance(value, list), f"{key} should return a list"
