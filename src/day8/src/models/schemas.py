"""
=============================================================================
FILE: src/models/schemas.py
COURSE: AI Agentic SRE - Day 8: Deep Dive — Agent Architectures
TOPIC:  Pydantic data models (schemas) for the EKS Investigation Agent
=============================================================================

PURPOSE:
  Defines all typed data structures used across the agent system.
  Pydantic gives us: runtime validation, auto-documentation, JSON
  serialisation, and IDE auto-complete — essential in production agents
  where the LLM output MUST conform to a known shape.

WHY SCHEMAS MATTER IN AGENTS:
  - LLM output is unstructured text by default → schemas enforce structure
  - Tools pass data between each other → a shared schema prevents bugs
  - Self-reflection needs to compare outputs → structured = comparable
  - Report generation needs typed inputs → schemas guarantee fields exist

ALGORITHM / READING ORDER:
  1. LogEntry         – a single parsed line from a log file
  2. K8sEvent         – a single parsed Kubernetes event
  3. PodAnalysis      – aggregated results for one pod
  4. Anomaly          – a detected problem with severity + evidence
  5. InvestigationPlan – list of steps (Plan-and-Execute pattern)
  6. ReflectionResult – output of the self-reflection check
  7. InvestigationReport – final output the agent writes to disk

REQUIREMENTS (pip install):
  pydantic>=2.0.0

=============================================================================
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# ENUMERATIONS  — fixed vocabulary prevents typos across the codebase
# ---------------------------------------------------------------------------

class LogLevel(str, Enum):
    """Mirrors standard syslog severity levels used in EKS pod logs."""
    INFO    = "INFO"
    WARNING = "WARNING"
    ERROR   = "ERROR"
    FATAL   = "FATAL"
    DEBUG   = "DEBUG"


class EventType(str, Enum):
    """Kubernetes event type — only two values exist in the K8s API."""
    NORMAL  = "Normal"
    WARNING = "Warning"


class AnomalySeverity(str, Enum):
    """
    How critical is the anomaly?
    HIGH   = needs immediate action (PagerDuty page)
    MEDIUM = investigate within 30 min (Slack alert)
    LOW    = track and review (ticket)
    """
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


class AnomalyType(str, Enum):
    """
    Categories of EKS/K8s anomalies the agent can detect.
    Extending this enum = extending what the agent can reason about.
    """
    OOMKILLED           = "OOMKILLED"           # Container killed by kernel OOM
    CRASHLOOPBACKOFF    = "CRASHLOOPBACKOFF"    # Pod restart loop
    MEMORY_LEAK         = "MEMORY_LEAK"         # Steadily growing memory
    CONNECTION_EXHAUSTION = "CONNECTION_EXHAUSTION"  # DB pool full
    NODE_MEMORY_PRESSURE  = "NODE_MEMORY_PRESSURE"  # Node-level risk
    HIGH_LATENCY        = "HIGH_LATENCY"        # Slow requests
    PROBE_FAILURE       = "PROBE_FAILURE"       # Readiness/liveness probe


# ---------------------------------------------------------------------------
# PRIMITIVE MODELS  — one log line or one event
# ---------------------------------------------------------------------------

class LogEntry(BaseModel):
    """
    Represents ONE parsed line from a pod log file.

    ALGORITHM:
      log_reader.py reads a raw line → regex extracts fields → LogEntry()
      The agent never sees raw strings; it always works with LogEntry objects.
    """
    timestamp:   datetime        = Field(..., description="When the event happened")
    level:       LogLevel        = Field(..., description="Severity level")
    service:     str             = Field(..., description="Service name e.g. web-service")
    pod_id:      str             = Field(..., description="Pod suffix e.g. 7d8b9c")
    message:     str             = Field(..., description="The log message")
    memory_mi:   Optional[float] = Field(None, description="Memory used in Mi if present")
    cpu_pct:     Optional[float] = Field(None, description="CPU % if present")
    latency_ms:  Optional[float] = Field(None, description="Request latency ms if present")
    exit_code:   Optional[int]   = Field(None, description="Process exit code if present")


class K8sEvent(BaseModel):
    """
    Represents ONE Kubernetes event from kubectl get events output.

    ALGORITHM:
      k8s_event_reader.py parses events file → K8sEvent()
      The agent uses these to correlate OOMKilled events with pod logs.
    """
    timestamp:  datetime  = Field(..., description="Event timestamp")
    event_type: EventType = Field(..., description="Normal or Warning")
    reason:     str       = Field(..., description="Reason code e.g. OOMKilled, BackOff")
    object_ref: str       = Field(..., description="pod/name or node/name")
    message:    str       = Field(..., description="Human-readable event description")
    count:      int       = Field(default=1, description="How many times this event fired")


# ---------------------------------------------------------------------------
# ANALYSIS MODELS  — aggregated results
# ---------------------------------------------------------------------------

class PodAnalysis(BaseModel):
    """
    Summary of log analysis for ONE pod.
    Created by the pattern_analyzer after reading all log lines for a pod.
    """
    pod_name:          str            = Field(..., description="Full pod name")
    namespace:         str            = Field(..., description="K8s namespace")
    log_file:          str            = Field(..., description="Source log file path")
    total_log_lines:   int            = Field(..., description="Total entries parsed")
    error_count:       int            = Field(..., description="Number of ERROR+ entries")
    warning_count:     int            = Field(..., description="Number of WARNING entries")
    error_rate_pct:    float          = Field(..., description="error_count/total * 100")
    peak_memory_mi:    Optional[float]= Field(None, description="Highest memory recorded")
    memory_trend:      str            = Field(default="STABLE",
                                              description="GROWING | STABLE | SHRINKING")
    top_errors:        List[str]      = Field(default_factory=list,
                                             description="Most common error messages")
    first_error_time:  Optional[str]  = Field(None, description="ISO timestamp of first error")
    last_error_time:   Optional[str]  = Field(None, description="ISO timestamp of last error")
    restart_count:     int            = Field(default=0, description="Pod restart count from events")


class Anomaly(BaseModel):
    """
    A detected problem with evidence and recommended action.

    DESIGN NOTE:
      The anomaly_detector produces these purely from data (no LLM).
      The LLM then uses the list of Anomaly objects to reason about
      root cause — separating detection (deterministic) from reasoning (LLM).
    """
    anomaly_id:        str           = Field(..., description="Unique ID e.g. ANO-001")
    anomaly_type:      AnomalyType   = Field(..., description="Category of anomaly")
    severity:          AnomalySeverity = Field(..., description="HIGH/MEDIUM/LOW")
    affected_resource: str           = Field(..., description="pod/name or node/name")
    detected_at:       str           = Field(..., description="When anomaly was detected")
    description:       str           = Field(..., description="Plain-English description")
    evidence:          List[str]     = Field(..., description="Log lines that prove this")
    runbook_ref:       Optional[str] = Field(None, description="Runbook filename e.g. RB-K8S-002.md")
    recommendation:    str           = Field(..., description="What the SRE should do")


# ---------------------------------------------------------------------------
# AGENT CONTROL MODELS  — Plan-and-Execute + Self-Reflection
# ---------------------------------------------------------------------------

class PlanStep(BaseModel):
    """
    ONE step in a Plan-and-Execute plan.

    The Planner LLM produces a list of these.
    The Executor agent then runs them in order.
    """
    step_number:  int           = Field(..., description="Step index starting at 1")
    description:  str           = Field(..., description="What this step does")
    tool_hint:    Optional[str] = Field(None,
                                        description="Which tool to use e.g. read_pod_logs")
    depends_on:   List[int]     = Field(default_factory=list,
                                        description="Step numbers that must complete first")
    completed:    bool          = Field(default=False)
    result:       Optional[str] = Field(None, description="Output after execution")


class InvestigationPlan(BaseModel):
    """
    Full Plan-and-Execute plan for an EKS investigation.

    The Planner LLM fills this in.
    The Executor agent updates `steps[i].completed` and `steps[i].result`.
    """
    plan_id:          str          = Field(..., description="Unique plan identifier")
    created_at:       str          = Field(..., description="Plan creation timestamp")
    objective:        str          = Field(..., description="What we are investigating")
    target_pod:       str          = Field(..., description="Pod under investigation")
    target_namespace: str          = Field(..., description="K8s namespace")
    steps:            List[PlanStep] = Field(..., description="Ordered list of steps")
    total_steps:      int          = Field(..., description="Count of steps")


class ReflectionResult(BaseModel):
    """
    Output of the self-reflection check after the agent produces an answer.

    ALGORITHM (self_reflection.py):
      1. Feed agent output to reflection prompt
      2. LLM checks completeness against a checklist
      3. Returns this model — is_complete=False triggers a second agent run
    """
    is_complete:      bool      = Field(...,
                                        description="True if analysis is sufficiently thorough")
    completeness_pct: int       = Field(..., description="0-100 completeness score")
    missing_items:    List[str] = Field(default_factory=list,
                                        description="What was not covered")
    quality_notes:    List[str] = Field(default_factory=list,
                                        description="Quality observations")
    follow_up_task:   Optional[str] = Field(None,
                                             description="Task for a second agent pass if needed")


# ---------------------------------------------------------------------------
# FINAL OUTPUT MODEL  — what gets saved to reports/
# ---------------------------------------------------------------------------

class InvestigationReport(BaseModel):
    """
    The final report written to disk by the agent.

    STRUCTURE mirrors a real SRE incident report:
      1. Executive summary (for managers)
      2. Timeline (for SREs)
      3. Root cause analysis (for engineers)
      4. Anomalies (for the on-call team)
      5. Recommendations (for action)
    """
    report_id:           str           = Field(..., description="Unique report ID")
    generated_at:        str           = Field(..., description="Report generation timestamp")
    investigation_target: str          = Field(..., description="Pod being investigated")
    namespace:           str           = Field(..., description="K8s namespace")
    executive_summary:   str           = Field(..., description="2-3 sentence summary for management")
    timeline_summary:    str           = Field(..., description="Chronological narrative of events")
    root_cause:          str           = Field(..., description="What actually caused the failure")
    contributing_factors: List[str]    = Field(..., description="Other factors that made it worse")
    anomalies_detected:  List[Anomaly] = Field(..., description="All anomalies found")
    recommendations:     List[str]     = Field(..., description="Ordered action items")
    severity:            str           = Field(..., description="P1/P2/P3/P4")
    pods_affected:       List[str]     = Field(..., description="All pods involved")
    duration_minutes:    Optional[int] = Field(None, description="How long the incident lasted")
    agent_mode:          str           = Field(..., description="REACT or PLAN_AND_EXECUTE")
    reflection_score:    Optional[int] = Field(None, description="Self-reflection completeness %")
