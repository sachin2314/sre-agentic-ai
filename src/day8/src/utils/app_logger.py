"""
=============================================================================
FILE: src/utils/app_logger.py
COURSE: AI Agentic SRE - Day 8: Deep Dive — Agent Architectures
TOPIC:  Structured application logger for the EKS Investigation Agent
=============================================================================

PURPOSE:
  Provides a consistent logging interface used across all modules.
  In production agents, good logging lets you trace EXACTLY what the
  agent reasoned at each step — essential for debugging agent failures.

WHY STRUCTURED LOGGING MATTERS FOR AGENTS:
  ReAct agents make many LLM calls. Without good logging you cannot:
  - Debug why the agent chose Tool A instead of Tool B
  - Measure latency of each Thought-Action-Observation cycle
  - Feed logs back into monitoring (CloudWatch, Datadog)
  - Audit agent decisions for compliance

ALGORITHM:
  1. Create a Python logger with a standard name
  2. Add console handler (always) + file handler (optional)
  3. Format includes timestamp, level, module — for easy grep
  4. Return configured logger to the calling module

REQUIREMENTS (pip install):
  None — uses Python stdlib logging only

=============================================================================
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Log format — matches CloudWatch Log format so SREs feel at home
# Example output:
# 2024-01-15T09:15:01Z | INFO  | react_agent    | Agent calling tool: read_pod_logs
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def get_logger(name: str, log_to_file: bool = True) -> logging.Logger:
    """
    Creates or retrieves a named logger instance.

    ALGORITHM:
      1. Get or create logger with the given name
      2. Set level to INFO (DEBUG available via env var)
      3. Add StreamHandler → console output
      4. Optionally add FileHandler → logs/agent_run.log
      5. Avoid duplicate handlers if called multiple times

    Args:
        name (str):         Module name e.g. "react_agent", "pod_log_reader"
        log_to_file (bool): Whether to also write logs to a file

    Returns:
        logging.Logger: configured logger for the module

    Example:
        logger = get_logger(__name__)
        logger.info("Starting pod log analysis")
        logger.error("Tool failed: %s", error_message)
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if this function is called multiple times
    # Python's logging module reuses loggers by name
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # -----------------------------------------------------------------------
    # Handler 1: Console (always active)
    # -----------------------------------------------------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
    )
    logger.addHandler(console_handler)

    # -----------------------------------------------------------------------
    # Handler 2: File (optional — creates logs/agent_run_<date>.log)
    # Keeping agent run logs on disk means you can review the full
    # Thought-Action-Observation trace after the fact.
    # -----------------------------------------------------------------------
    if log_to_file:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"agent_run_{today}.log"

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)   # Capture DEBUG in file even if console shows INFO
        file_handler.setFormatter(
            logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
        )
        logger.addHandler(file_handler)

    # Do not propagate to root logger (prevents duplicate output)
    logger.propagate = False

    return logger


def get_agent_step_logger() -> logging.Logger:
    """
    Special logger for ReAct Thought-Action-Observation steps.
    Uses a distinct name so you can grep logs for just agent reasoning.

    Returns:
        logging.Logger: logger named "AGENT_STEP"
    """
    return get_logger("AGENT_STEP")
