# Runbook: CloudWatch Log Analyst Agent — Operation & Troubleshooting

**Type:** Operational Runbook (not incident response)
**Purpose:** How to run, configure, and troubleshoot the Day 7 log analyst agent

---

## 1. What This Agent Does

The CloudWatch Log Analyst Agent is a 6-step pipeline that:
1. Loads log files from `logs/`
2. Parses them into structured data
3. Detects anomalies using 3 patterns (threshold, statistical, keyword)
4. Correlates anomalies into incident patterns
5. Optionally runs LLM root cause analysis
6. Writes a Markdown report to `reports/`

---

## 2. Prerequisites

**Python version:** 3.10 or higher

**Install dependencies:**
```bash
cd day7-cloudwatch-log-analyst
pip install -r requirements.txt
```

**Optional (for LLM root cause analysis):**
```bash
export OPENAI_API_KEY=sk-your-key-here
```

---

## 3. Running the Agent

### Run the full pipeline (recommended):
```bash
# From the project root
cd day7-cloudwatch-log-analyst
python src/step7_full_pipeline.py
```

### Run individual steps (for learning / debugging):
```bash
python src/step1_load_logs.py       # Just load files
python src/step2_parse_logs.py      # Load + parse
python src/step3_anomaly_detection.py  # Detect anomalies
python src/step4_pattern_analysis.py   # Pattern analysis
python src/step5_root_cause.py      # RCA (needs API key)
python src/step6_report_generator.py   # Generate report (no API key needed)
```

### Run tests:
```bash
cd day7-cloudwatch-log-analyst
pytest tests/ -v
```

---

## 4. Configuration

### Tuning anomaly detection thresholds

Open `src/step3_anomaly_detection.py` and adjust:

```python
# Threshold detection: change how many errors/min triggers an alert
detect_threshold_anomalies(entries, error_threshold=3)   # default: 3

# Statistical detection: change z-score sensitivity
detect_statistical_anomalies(entries, z_threshold=2.0)   # default: 2.0
```

**Lower threshold → more sensitive → more false positives**
**Higher threshold → less sensitive → may miss real incidents**

### Adding new keywords

In `src/step3_anomaly_detection.py`, add to the lists:

```python
CRITICAL_KEYWORDS = [
    "OOMKilling",
    "Out of memory",
    "your-new-critical-keyword",   # add here
    ...
]
```

### Adding a new log source

1. Add the filename to `LOG_FILES` in `step1_load_logs.py`
2. Write a `parse_<source>_log(lines)` function in `step2_parse_logs.py`
3. Call it inside `parse_all_logs()` in `step2_parse_logs.py`
4. Add any source-specific keywords to `step3_anomaly_detection.py`

---

## 5. Troubleshooting

### "File not found" for log files
```
[WARNING] File not found: .../logs/app.log
```
**Fix:** Make sure you are running the script from the project root folder, not from inside `src/`.
```bash
# Correct:
cd day7-cloudwatch-log-analyst
python src/step7_full_pipeline.py

# Wrong (will fail):
cd day7-cloudwatch-log-analyst/src
python step7_full_pipeline.py
```

### "OPENAI_API_KEY is not set"
The agent will skip LLM root cause analysis and use rule-based analysis instead. This is fine — you'll still get a full report.

To add LLM analysis:
```bash
export OPENAI_API_KEY=sk-...
python src/step7_full_pipeline.py
```

### "ModuleNotFoundError: No module named 'langchain_openai'"
```bash
pip install langchain-openai --break-system-packages
```

### No anomalies detected
- Check that your log files are in the `logs/` folder
- Check that the log format matches the regex patterns in `step2_parse_logs.py`
- Try lowering the threshold: `error_threshold=1`

### Report not generated
- Check that the `reports/` folder exists: `mkdir -p reports`
- Check file permissions on the reports folder

---

## 6. Output Files

| Location | Description |
|----------|-------------|
| `logs/*.log` | Input: fake log files |
| `reports/incident_report_YYYYMMDD_HHMMSS.md` | Output: analysis report |

---

## 7. Project File Map

```
day7-cloudwatch-log-analyst/
├── src/
│   ├── step1_load_logs.py          # Load raw files
│   ├── step2_parse_logs.py         # Parse into dicts
│   ├── step3_anomaly_detection.py  # 3 detection patterns
│   ├── step4_pattern_analysis.py   # Correlate & cluster
│   ├── step5_root_cause.py         # LLM RCA via LangChain
│   ├── step6_report_generator.py   # Build Markdown report
│   └── step7_full_pipeline.py      # Orchestrator (run this)
├── logs/                           # Fake log files (input)
├── reports/                        # Generated reports (output)
├── runbooks/                       # This file + incident runbooks
├── tests/                          # Pytest tests
├── docs/theory.md                  # Full theory notes
└── requirements.txt
```

---

*Runbook owner: SRE Learning — Day 7 | Review: After each sprint*
