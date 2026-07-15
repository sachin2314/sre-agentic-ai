"""
Integration test for step7_full_pipeline.py
Tests the full agent pipeline end-to-end (without LLM).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from step7_full_pipeline import LogAnalystAgent


class TestLogAnalystAgent:

    @pytest.fixture
    def agent(self):
        """Create an agent with LLM disabled (no API key needed)."""
        return LogAnalystAgent(use_llm=False)

    def test_agent_initialises(self, agent):
        """Agent should initialise without error."""
        assert agent is not None
        assert agent.use_llm is False

    def test_step1_load_populates_raw_logs(self, agent):
        agent.step1_load()
        assert agent.raw_logs is not None
        assert "app.log" in agent.raw_logs

    def test_step2_parse_populates_entries(self, agent):
        agent.step1_load()
        agent.step2_parse()
        assert agent.entries is not None
        assert len(agent.entries) > 0

    def test_step3_detect_finds_anomalies(self, agent):
        agent.step1_load()
        agent.step2_parse()
        agent.step3_detect()
        assert agent.anomalies is not None
        assert len(agent.anomalies) > 0

    def test_step4_correlate_finds_patterns(self, agent):
        agent.step1_load()
        agent.step2_parse()
        agent.step3_detect()
        agent.step4_correlate()
        assert agent.patterns is not None
        assert len(agent.patterns) > 0

    def test_full_run_creates_report_file(self, agent, tmp_path, monkeypatch):
        """run() should produce a report file on disk."""
        import step6_report_generator as rg
        monkeypatch.setattr(rg, "REPORTS_DIR", str(tmp_path))

        report_path = agent.run()

        assert report_path is not None
        assert os.path.exists(report_path)

    def test_report_file_is_not_empty(self, agent, tmp_path, monkeypatch):
        """The report file should have content."""
        import step6_report_generator as rg
        monkeypatch.setattr(rg, "REPORTS_DIR", str(tmp_path))

        report_path = agent.run()

        with open(report_path) as f:
            content = f.read()

        assert len(content) > 100  # a real report is much longer than 100 chars

    def test_entries_are_sorted_by_timestamp(self, agent):
        """Parsed entries should be sorted chronologically."""
        agent.step1_load()
        agent.step2_parse()
        timestamps = [e["timestamp"] for e in agent.entries]
        assert timestamps == sorted(timestamps)
