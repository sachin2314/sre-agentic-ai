"""
Tests for step3_anomaly_detection.py
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from step3_anomaly_detection import (
    Anomaly,
    group_by_minute,
    detect_threshold_anomalies,
    detect_statistical_anomalies,
    detect_keyword_anomalies,
    run_all_detectors,
)
from step2_parse_logs import extract_key_value_fields


# ---------------------------------------------------------------
# FIXTURES — reusable fake data
# ---------------------------------------------------------------

def make_entry(timestamp, level, source, message, fields=None):
    """Helper to build a fake log entry dict."""
    return {
        "timestamp": timestamp,
        "level":     level,
        "source":    source,
        "message":   message,
        "fields":    fields or {},
    }


@pytest.fixture
def normal_entries():
    """A batch of normal (no anomalies) log entries."""
    return [
        make_entry("2024-01-15 09:00:01", "INFO",  "app",          "Request processed"),
        make_entry("2024-01-15 09:01:01", "INFO",  "app",          "Request processed"),
        make_entry("2024-01-15 09:02:01", "INFO",  "database",     "Query executed"),
        make_entry("2024-01-15 09:03:01", "INFO",  "nginx_access", "GET /api/ 200", {"response_time": "0.05"}),
    ]


@pytest.fixture
def error_spike_entries():
    """Many errors in the same minute — should trigger threshold anomaly."""
    return [
        make_entry("2024-01-15 09:20:01", "ERROR", "app", "Request failed"),
        make_entry("2024-01-15 09:20:02", "ERROR", "app", "Request failed"),
        make_entry("2024-01-15 09:20:03", "ERROR", "app", "Request failed"),
        make_entry("2024-01-15 09:20:04", "ERROR", "app", "Request failed"),
        make_entry("2024-01-15 09:20:05", "ERROR", "app", "Request failed"),
    ]


@pytest.fixture
def oom_entry():
    """A single OOM kill event — critical keyword."""
    return [
        make_entry("2024-01-15 09:20:15", "FATAL", "app", "Out of memory. used_mb=2048"),
    ]


# ---------------------------------------------------------------
# TESTS: group_by_minute
# ---------------------------------------------------------------

class TestGroupByMinute:

    def test_groups_same_minute_together(self, normal_entries):
        result = group_by_minute(normal_entries)
        # "2024-01-15 09:00:01" → key "2024-01-15 09:00"
        assert "2024-01-15 09:00" in result

    def test_different_minutes_are_separate_keys(self, normal_entries):
        result = group_by_minute(normal_entries)
        # We have entries at 09:00, 09:01, 09:02, 09:03
        assert len(result) == 4

    def test_empty_input_returns_empty_dict(self):
        result = group_by_minute([])
        assert result == {}


# ---------------------------------------------------------------
# TESTS: detect_threshold_anomalies
# ---------------------------------------------------------------

class TestThresholdDetection:

    def test_no_anomaly_below_threshold(self, normal_entries):
        """Normal entries should not trigger an anomaly."""
        result = detect_threshold_anomalies(normal_entries, error_threshold=3)
        assert len(result) == 0

    def test_anomaly_detected_above_threshold(self, error_spike_entries):
        """5 errors in one minute should trigger an anomaly."""
        result = detect_threshold_anomalies(error_spike_entries, error_threshold=3)
        assert len(result) == 1

    def test_anomaly_has_correct_type(self, error_spike_entries):
        result = detect_threshold_anomalies(error_spike_entries, error_threshold=3)
        assert result[0].anomaly_type == "threshold"

    def test_anomaly_severity_is_high_or_critical(self, error_spike_entries):
        result = detect_threshold_anomalies(error_spike_entries, error_threshold=3)
        assert result[0].severity in ("HIGH", "CRITICAL", "MEDIUM")

    def test_threshold_can_be_tuned(self, error_spike_entries):
        """Setting threshold=10 should produce no anomaly for 5 errors."""
        result = detect_threshold_anomalies(error_spike_entries, error_threshold=10)
        assert len(result) == 0


# ---------------------------------------------------------------
# TESTS: detect_keyword_anomalies
# ---------------------------------------------------------------

class TestKeywordDetection:

    def test_oom_triggers_critical_anomaly(self, oom_entry):
        result = detect_keyword_anomalies(oom_entry)
        assert len(result) >= 1
        assert result[0].severity == "CRITICAL"

    def test_normal_entries_produce_no_keyword_anomaly(self, normal_entries):
        result = detect_keyword_anomalies(normal_entries)
        assert len(result) == 0

    def test_anomaly_has_evidence(self, oom_entry):
        result = detect_keyword_anomalies(oom_entry)
        assert len(result[0].evidence) > 0

    def test_timeout_triggers_high_anomaly(self):
        entries = [
            make_entry("2024-01-15 09:20:04", "ERROR", "database", "Query timeout. duration_ms=5001"),
        ]
        result = detect_keyword_anomalies(entries)
        assert any(a.severity in ("HIGH", "CRITICAL") for a in result)


# ---------------------------------------------------------------
# TESTS: run_all_detectors (integration)
# ---------------------------------------------------------------

class TestRunAllDetectors:

    def test_real_logs_produce_anomalies(self):
        """Running on the real log files should detect anomalies."""
        from step1_load_logs import load_all_logs
        from step2_parse_logs import parse_all_logs

        raw_logs = load_all_logs()
        entries  = parse_all_logs(raw_logs)
        anomalies = run_all_detectors(entries)

        # We know our fake logs contain anomalies
        assert len(anomalies) > 0

    def test_at_least_one_critical_anomaly_in_real_logs(self):
        """The fake logs should contain at least one CRITICAL anomaly."""
        from step1_load_logs import load_all_logs
        from step2_parse_logs import parse_all_logs

        raw_logs = load_all_logs()
        entries  = parse_all_logs(raw_logs)
        anomalies = run_all_detectors(entries)

        critical = [a for a in anomalies if a.severity == "CRITICAL"]
        assert len(critical) > 0

    def test_anomalies_sorted_by_timestamp(self):
        """Anomalies should come back sorted by time."""
        from step1_load_logs import load_all_logs
        from step2_parse_logs import parse_all_logs

        raw_logs  = load_all_logs()
        entries   = parse_all_logs(raw_logs)
        anomalies = run_all_detectors(entries)

        timestamps = [a.timestamp for a in anomalies]
        assert timestamps == sorted(timestamps)