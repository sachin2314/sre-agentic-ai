# Day 7: CloudWatch Log Analyst Agent
## Portfolio Project 1 — SRE AI Agents Curriculum

---

## What This Project Does

This is an end-to-end log analysis pipeline agent. It:
1. Loads log files from the `logs/` folder
2. Parses them into structured data
3. Detects anomalies using 3 detection patterns (threshold, statistical, keyword)
4. Correlates anomalies into incident patterns (cross-log correlation)
5. Optionally runs LLM-powered root cause analysis (requires OpenAI API key)
6. Generates a full Markdown incident report saved to `reports/`

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the full pipeline (no API key needed)
python src/step7_full_pipeline.py

# 3. Run with LLM root cause analysis
export OPENAI_API_KEY=sk-...
python src/step7_full_pipeline.py

# 4. Run tests
pytest tests/ -v
```

---

## Project Structure

```
day7-cloudwatch-log-analyst/
├── src/
│   ├── step1_load_logs.py          # Load raw log files
│   ├── step2_parse_logs.py         # Parse into structured dicts
│   ├── step3_anomaly_detection.py  # 3 detection patterns
│   ├── step4_pattern_analysis.py   # Cluster & correlate anomalies
│   ├── step5_root_cause.py         # LLM root cause analysis
│   ├── step6_report_generator.py   # Generate Markdown report
│   └── step7_full_pipeline.py      # Full pipeline agent (run this)
│
├── logs/                           # Fake log files (input)
│   ├── app.log
│   ├── nginx_access.log
│   ├── nginx_error.log
│   ├── database.log
│   └── kubernetes_events.log
│
├── reports/                        # Generated reports (output)
│
├── runbooks/
│   ├── db_connection_pool_exhaustion_runbook.md
│   └── anomaly_detection_agent_runbook.md
│
├── tests/
│   ├── test_log_loader.py
│   ├── test_anomaly_detection.py
│   ├── test_report_generator.py
│   └── test_pipeline.py
│
├── docs/
│   └── theory.md                   # Full theory, patterns, interview Q&A
│
├── requirements.txt
└── README.md
```

---

## The Incident in the Fake Logs

The fake logs simulate a P1 incident cascade:

```
09:18 → DB autovacuum causes table lock on 'orders'
09:19 → Lock contention → slow queries (1200ms–4800ms)
09:20 → DB connection pool exhausted (200/200)
09:20 → App servers timeout, OOM killed
09:20 → Kubernetes kills all pods (liveness probe fails)
09:20 → Pod quota exceeded → HPA can't scale → 502 for all users
09:22 → DB recovers → app restarts → service restored
```

---

## How to Learn from This Project

Run each step file individually to understand what it does:

```bash
python src/step1_load_logs.py       # See what loading does
python src/step2_parse_logs.py      # See parsed entries
python src/step3_anomaly_detection.py  # See anomalies found
python src/step4_pattern_analysis.py   # See incident patterns
python src/step6_report_generator.py   # See the report
```

Then read `docs/theory.md` for the full explanation of every concept.

---

## Day 6 vs Day 7

| | Day 6 (ReAct Agent) | Day 7 (Pipeline Agent) |
|--|--|--|
| Trigger | Incident in progress | Scheduled / proactive |
| Control flow | LLM-driven (dynamic) | Code-driven (fixed steps) |
| Goal | Resolve incident | Detect + report |
| Output | Chat diagnosis | Saved report file |
