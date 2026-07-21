# Day 8: Deep Dive — Agent Architectures
### AI Agentic SRE Course | Week 2

**SRE Application:** "Investigate EKS pod failure"  
**Deliverable:** ReAct + Plan-and-Execute Agent with Self-Reflection  
**Model:** `eu.anthropic.claude-haiku-4-5-20251001-v1:0` (AWS Bedrock EU Cross-Region Inference)

---

## 📌 Day 6 vs Day 8 — Key Differences

| Dimension | Day 6 — First SRE Agent | Day 8 — Deep Dive |
|-----------|------------------------|-------------------|
| **Architecture** | Basic ReAct (introduced) | ReAct + Plan-and-Execute (mastered) |
| **Tools** | 1 tool (log reader) | 3 tools (pod logs + K8s events + node metrics) |
| **Self-evaluation** | Hallucination guardrails | Full self-reflection loop with score |
| **Agent patterns** | ReAct only | ReAct AND Plan-and-Execute (two distinct patterns) |
| **Failure modes** | Not covered | "Why agents fail" — explicit coverage |
| **SRE domain** | CloudWatch (AWS Lambda) | EKS pod failures (Kubernetes) |
| **Output** | Text summary | Structured report + reflection metadata |
| **Planning** | Reactive (one step at a time) | Proactive (full plan before execution) |

**Reasoning:** Day 6 *introduces* ReAct as a concept. Day 8 takes it apart, shows its internals,
adds a second architecture (Plan-and-Execute), and layers self-reflection on top. Day 8 also
shifts to K8s/EKS — a more complex domain that benefits from structured planning.

---

## 🧠 Theory

### 1. ReAct (Reason + Act) — Deep Dive

ReAct is not just "the LLM calls tools." It is a specific loop with 4 distinct phases:

```
THOUGHT  → LLM reasons: "I need to check K8s events after seeing OOMKilled in logs"
ACTION   → LLM decides: read_k8s_events
ACTION INPUT → LLM provides: {"namespace": "production", "pod_name": "web-service-7d8b9c"}
OBSERVATION → Tool runs → result injected into context
↑_____________repeat_____________|
          until: FINAL ANSWER
```

**Why it works:** The LLM never executes code. It only *reasons* about what to call.
The framework executes. This separation makes it safe and auditable.

**Why it fails (Day 8 covers this):**
- **Infinite loops:** Agent keeps calling same tool, getting same result, calling again
- **Tool hallucination:** Agent "calls" a tool that doesn't exist
- **Premature stop:** Agent declares Final Answer without enough evidence
- **Context overflow:** Long observations fill the context window, agent loses earlier info
- **Brittle parsing:** LLM produces "Thought:" in wrong format → parser breaks

### 2. Plan-and-Execute — Architecture

```
INPUT
  ↓
PLANNER LLM (no tools)
  → "Step 1: list_available_pods"
  → "Step 2: read_pod_logs for web-service-7d8b9c"
  → "Step 3: read_k8s_events"
  → "Step 4: read_node_metrics (if OOMKilled found)"
  → "Step 5: synthesise"
  ↓
EXECUTOR (has tools, runs each step)
  ↓
SYNTHESISER LLM (no tools)
  → Writes final report from all step results
```

**When to use Plan-and-Execute vs ReAct:**

| Situation | Use |
|-----------|-----|
| Investigation workflow is well-known | Plan-and-Execute |
| Novel problem, unknown investigation path | ReAct |
| You need to ensure specific steps always run | Plan-and-Execute |
| Maximum flexibility needed | ReAct |
| Production system with compliance audit trail | Plan-and-Execute |

### 3. Self-Reflection Loop

```python
# Pseudocode — see self_reflection.py for full implementation
result = agent.run(task)
for i in range(max_reflections):
    reflection = reflection_llm.evaluate(result)
    if reflection.is_complete:
        break
    result += agent.run(reflection.follow_up_task)
```

**The reflection checklist (applied internally):**
1. Root cause identified with specific evidence?
2. Timeline constructed with timestamps?
3. All resources checked (pod + node)?
4. Recommendations specific and actionable?
5. Runbook referenced?
6. Blast radius assessed?
7. Prevention measures included?

### 4. Why Agents Fail — Production Reality

| Failure Mode | Example | Fix |
|---|---|---|
| **Infinite loop** | Agent calls same tool 15 times | `max_iterations=15` in AgentExecutor |
| **Tool hallucination** | Calls `get_rds_metrics` (doesn't exist) | Strict tool name validation |
| **Context overflow** | 10,000 token observation fills context | Truncate tool outputs |
| **Premature stop** | Stops after 1 tool call | Self-reflection catches this |
| **Brittle parsing** | "thought:" instead of "Thought:" | `handle_parsing_errors=True` |
| **Stale planning** | Plan made for pod X, events show pod Y | Replanner step |
| **Tool failures** | boto3 credential error mid-investigation | Per-step try/except |

---

## 🗂️ Folder Structure

```
day8-eks-investigation-agent/
│
├── main.py                         # Entry point — CLI
├── requirements.txt                # pip dependencies
├── .env.example                    # → copy to .env
├── .gitignore
│
├── logs/                           # FAKE EKS logs (no AWS needed)
│   ├── eks_pod_web_service_7d8b9c.log      # Failing pod (OOM leak)
│   ├── eks_pod_api_gateway_6f9a2b.log      # Healthy comparison pod
│   ├── k8s_events_production.log           # K8s events (OOMKilled etc.)
│   └── k8s_node_metrics.log               # Node memory pressure data
│
├── runbooks/                       # SRE runbooks
│   ├── RB-K8S-001-crashloopbackoff.md
│   ├── RB-K8S-002-oomkilled.md
│   ├── RB-K8S-003-node-memory-pressure.md
│   └── RB-K8S-004-connection-pool-exhaustion.md
│
├── reports/                        # Agent-generated reports (auto-created)
│   └── .gitkeep
│
└── src/
    ├── agent/
    │   ├── react_agent.py          # ⭐ ReAct agent with AgentExecutor
    │   ├── plan_and_execute_agent.py  # ⭐ Plan-and-Execute agent
    │   └── self_reflection.py      # ⭐ Self-reflection quality loop
    │
    ├── tools/
    │   ├── pod_log_reader.py       # Tool 1: read EKS pod logs
    │   └── k8s_event_reader.py     # Tool 2: read K8s events + node metrics
    │
    ├── models/
    │   └── schemas.py              # Pydantic models for all data
    │
    └── utils/
        ├── bedrock_client.py       # AWS Bedrock LLM factory
        └── app_logger.py           # Structured logging
```

---

## 🚀 Quick Start

```bash
# 1. Clone and enter directory
cd day8-eks-investigation-agent

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure AWS credentials
cp .env.example .env
# Edit .env: add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

# 5. Run ReAct investigation (recommended)
python main.py --mode react --pod web-service-7d8b9c

# 6. Run Plan-and-Execute
python main.py --mode plan --pod web-service-7d8b9c

# 7. Compare both architectures (educational)
python main.py --mode compare --pod web-service-7d8b9c
```

---

## ⚠️ Production Issues

1. **Token cost at scale** — Each ReAct iteration = one LLM call. 15 iterations = 15 calls
2. **Agent latency** — ReAct with reflection can take 60-120s. Use async for production
3. **Tool reliability** — K8s API flakes → add retry logic to each tool
4. **Context window limits** — Long log files overflow Haiku's context → truncate outputs
5. **Credential rotation** — Bedrock clients cache credentials → refresh on 401

## ✅ Best Practices

1. Always set `max_iterations` in AgentExecutor (prevents infinite loops)
2. Truncate tool outputs (keep context window manageable)
3. Use `temperature=0` for deterministic agent behaviour
4. Keep tools FOCUSED — one tool does one thing well
5. Log every Thought/Action/Observation for debugging
6. Test tools independently before wiring into agents

## 🚧 Live Implementation Blockers

1. **IAM permissions** — Bedrock `InvokeModel` + cross-region inference profile access required
2. **VPC routing** — Bedrock endpoint may not be reachable from EKS pods in private subnets
3. **K8s RBAC** — Agent service account needs `get`, `list` on pods, events
4. **CloudWatch API limits** — `GetLogEvents` is throttled at 10 req/s per log group
5. **Cost governance** — No cost caps on agent LLM calls without AWS Budgets alerts
RUNBOOK

---

## 🎯 Interview Questions

**Q1: What is the difference between ReAct and Plan-and-Execute?**
> ReAct is reactive — each step decides the next. Plan-and-Execute creates a full plan upfront then executes it. ReAct is more flexible for novel problems; Plan-and-Execute is more predictable for known workflows.

**Q2: What is self-reflection in agents?**
> After the agent produces output, a second LLM call evaluates completeness against a checklist. If incomplete, the agent runs again with a targeted follow-up task. Based on the Reflexion paper (2023).

**Q3: Why does `temperature=0` matter for SRE agents?**
> Deterministic output means the same incident produces the same plan and recommendations. This is critical for reproducibility, testing, and compliance.

**Q4: How do you prevent an agent from running forever?**
> Set `max_iterations` in AgentExecutor. Also use self-reflection with a max cycle limit, and set LLM timeout via boto3 client config.

**Q5: What IAM permissions does a Bedrock ReAct agent need?**
> `bedrock:InvokeModel` for the specific model ARN, plus inference profile access if using cross-region routing. For EKS deployment: attach via IRSA (IAM Roles for Service Accounts).
