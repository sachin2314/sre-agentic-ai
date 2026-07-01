# Day 6 — SRE Agent Theory & Reference Guide

---

## BEFORE YOU READ: Does Day 5 (Vector DB) Connect to Day 6?

**Short answer: No, not directly — but it will connect in later days.**

Day 5 was about storing and searching *knowledge* (embedding text into vectors, storing in Chroma/FAISS).

Day 6 is about *acting* (reading live logs, making decisions, writing RCAs).

They will connect when we build a smarter agent that can:
- Use a vector DB to search past RCAs ("have we seen this failure mode before?")
- Retrieve relevant runbook sections based on the current incident
- Store agent memories across incidents

For now, Day 6 stands completely alone. No vector DB needed.

---

## PART 1 — CORE THEORY

### 1.1 What Problem Does an SRE Agent Solve?

Without an agent, a P1 incident looks like this:

```
3:00 AM — PagerDuty fires
3:04 AM — Engineer opens laptop, checks Slack
3:06 AM — Opens CloudWatch, filters for errors
3:09 AM — Opens another tab for Kubernetes events
3:12 AM — Opens another tab for Postgres slow query logs
3:16 AM — Starts piecing together what happened
3:25 AM — Finally understands the root cause
3:40 AM — Fix applied
```

That is 40 minutes of MTTR (Mean Time to Recover). Most of that is just reading and correlating logs.

**An SRE agent compresses the log-reading part from 20 minutes to under 60 seconds.**

---

### 1.2 What is the ReAct Pattern?

ReAct = **Re**ason + **Act**

It was published in a 2022 paper: "ReAct: Synergizing Reasoning and Acting in Language Models".

The key idea: reasoning and action should happen in small interleaved cycles, not all at once.

**The wrong way (think everything, then act):**
```
"I think the problem might be OOM, or maybe network, or maybe disk, 
 or maybe DNS, or maybe the deploy, or maybe the database..." 
→ takes 10 minutes, makes wrong decisions without evidence
```

**The ReAct way (think a little, act, see result, think again):**
```
Iteration 1:  THINK: I'll check app logs first
              ACT:   read app logs
              OBSERVE: Found OOM kill at 08:01:55
              
Iteration 2:  THINK: OOM found. Check K8s to confirm.
              ACT:   read kubernetes events  
              OBSERVE: OOMKilling confirmed. Quota also full.
              
Iteration 3:  THINK: Check how many users hit 502s
              ACT:   count 502 errors in nginx
              OBSERVE: 5 requests failed
...
```

Each step is grounded in real data. Each thought is informed by what was just found.

---

### 1.3 The Three Phases — Deeply Explained

#### THINK (Reason)
The agent looks at its current state and decides the single best next step.

Key questions the THINK step answers:
- What do I already know?
- What is the most important gap in my knowledge?
- Which tool would fill that gap?
- Do I have enough to finish, or do I need more?

In code, this is the `think()` function in `step4_think.py`. Notice it uses `if/elif` chains to represent this reasoning as simple rules.

In a real LLM-based agent, you would send the current state to GPT-4 or Claude and ask it to decide. Our version uses deterministic rules instead — easier to learn, easier to trust.

#### ACT (Action)
The agent calls a tool. That's it. Nothing more complex.

Key properties of good tools:
- **Do one thing only** — `read_app_logs()` only reads app logs
- **Read-only** — they observe, they don't change anything
- **Return structured data** — list of strings, or a dict

#### OBSERVE (Observation)
The agent reads the tool output and extracts the signal from the noise.

Out of 100 log lines, maybe 8 are interesting. The OBSERVE step throws away the boring 92 lines and keeps only the 8 that matter.

Those 8 lines go into the `findings` list which the next THINK step will use.

---

### 1.4 Agent Memory — What the Agent "Knows"

The agent has three types of memory in our implementation:

| Memory type | Variable | What it stores |
|-------------|----------|----------------|
| Working memory | `findings` | Key findings from this incident |
| Tool usage | `tools_used` | Which tools have been called |
| Evidence | `all_evidence` | Raw log lines (used by guardrail) |
| Trace | `trace` | The full THINK/ACT/OBSERVE history |

This is all **in-memory for one run**. When the agent finishes, this is gone. In production you would write the trace and RCA to a database.

---

### 1.5 Hallucination — The Most Important Concept

**What is hallucination?**

An AI model (or even a rule-based system) can produce a confident, grammatically correct statement that is completely wrong and unsupported by any evidence.

Example:
- **Log evidence collected**: OOM kill at 08:01:55, connection refused, quota exceeded
- **Agent claims**: "Root cause was a DNS failure in the VPC service mesh"
- **Problem**: No DNS evidence anywhere. The agent made this up.

**Why does hallucination happen?**
- Pattern matching on training data — "production outages" often involve DNS in the training data
- The model fills gaps with statistically likely but incorrect explanations
- Nothing is anchoring claims to the actual evidence

**Why is it dangerous in SRE?**
- Engineers are tired and stressed at 3am — they trust the agent
- They spend 2 hours debugging DNS while the real problem goes unfixed
- Trust in the agent tool is destroyed after one bad incident

**How we prevent it:**
```
CITATION-ONLY RCA
Every claim must link back to a log line.
No log line? No claim.
```

Our `step6_hallucination_guard.py` does this by:
1. Extracting keywords from each claim ("OOM", "connection", "502", etc.)
2. Searching the actual evidence lines for those keywords
3. Scoring confidence: 0.0 (no match) to 1.0 (full match)
4. Removing claims below the confidence threshold

---

### 1.6 The Incident We Simulated — Full Cascade

```
TIME      EVENT
────────────────────────────────────────────────────────────
08:00:00  App starts, memory at 200MB / 512MB — normal
08:01:00  Memory grows to 380MB — app caching too much data
08:01:20  DB slow queries taking 8+ seconds — connections held open
08:01:30  DB max connections hit — new connections refused
08:01:50  OOM error — cannot allocate memory for cache
08:01:55  OOM killer kills the process (exit code 137)
08:02:00  App tries to restart (attempt 1)
08:02:01  Restart fails — DB connection still refused (connections not freed)
08:02:04  App tries to restart (attempt 2)
08:02:05  Restart fails again
08:02:07  All restart attempts exhausted — pod stuck in CrashLoopBackOff
08:02:01  Nginx: no upstreams available → 502 to all users
08:02:45  HPA tries to scale from 3 to 6 pods
08:03:00  Scale-out fails — pod quota is 10/10 already full
────────────────────────────────────────────────────────────
```

The key insight: **this is a cascade**. Each failure caused the next. Finding the ROOT cause (unbounded memory cache + slow queries) is more valuable than fixing each symptom individually.

---

## PART 2 — PRODUCTION ISSUES (2026)

### What Breaks in Production with SRE Agents

**Issue 1: Log Volume**
Our test logs have 10 lines each. Real production logs have millions of lines per minute. You can't read them all. You need time-bounded, level-filtered queries.

Fix: Always query with a time window (last 5 minutes, not all time).

**Issue 2: Log Format Changes**
A team changes their log format. Your parser breaks silently. The agent sees 0 lines and reports "no issues found" during a live incident.

Fix: Add an assertion that log reads return at least N lines. Alert if the format looks wrong.

**Issue 3: False Confidence**
The agent reports "Root cause found: OOM" with high confidence. But the OOM was a symptom — the real cause was a memory leak introduced in yesterday's deploy.

Fix: Always include "contributing factors" and "what changed recently" in the RCA template.

**Issue 4: The Agent Itself Fails During an Incident**
The agent crashes because a log file is missing, or a regex breaks, or a dependency is down. Now you have a broken incident tool AND a broken service.

Fix: Every tool call is wrapped in try/except. The agent always produces output, even if some tools failed.

**Issue 5: Engineers Don't Trust It**
After one wrong RCA, engineers stop reading the agent output and go back to manual log reading.

Fix: Show the evidence. The guardrail transparency section shows exactly what was verified. Engineers can see the logic.

**Issue 6: Security — Logs Contain PII**
Database query logs often contain email addresses, user IDs, IP addresses. The agent reads them all and puts them in the RCA which gets shared in Slack.

Fix: Add a PII scrubber middleware that replaces emails, IPs, UUIDs with placeholders before the agent sees the logs.

---

## PART 3 — BEST PRACTICES

### Agent Design

**Always set MAX_ITERATIONS**
Without it, a bug causes an infinite loop. 10 is enough for most incidents. In production, set it lower (6-8) and alert if the agent hits the limit.

**Tools should be read-only**
Never let the agent execute destructive commands. Fixes go in the RCA as recommendations. A human (or a separate approval workflow) runs them.

**Start specific, not broad**
Don't read all logs for all services for all time. Start with the alerting service, the last 15 minutes.

**Fail loudly, not silently**
If a tool fails, say so in the output. `"[TOOL ERROR] Could not read app logs: Permission denied"` is infinitely better than the agent silently skipping that step.

**Make the reasoning visible**
Log every THOUGHT. Engineers reading the agent trace should be able to follow exactly why each decision was made.

### Hallucination Prevention

**Citation-only**: every RCA claim is checked against the evidence lines.

**Confidence scoring**: don't just pass/fail. Show the score so engineers know how certain each claim is.

**Show what was removed**: the guardrail transparency section lists every claim that was removed and why. This builds trust.

**Human review for P0/P1**: even with a guardrail, have a human approve the RCA before it goes into the incident ticket.

### Log Design (for the agent to work well)

```
GOOD LOG FORMAT:
2026-06-26T08:01:55Z FATAL [app] OutOfMemoryError: allocate 64MB for product_catalog

BAD LOG FORMAT:
!! PROBLEM at 8am - memory died !!
```

Good logs have: ISO timestamp, severity level, component, specific error type.

---

## PART 4 — FOLDER STRUCTURE (LIVE-LIKE)

```
sre-agent-day6-simple/
│
├── src/                          ← All Python source code
│   ├── step1_read_logs.py        ← Building block 1: read files
│   ├── step2_search_logs.py      ← Building block 2: find errors
│   ├── step3_tools.py            ← Building block 3: tool registry
│   ├── step4_think.py            ← Building block 4: reasoning
│   ├── step5_observe.py          ← Building block 5: observations
│   ├── step6_hallucination_guard.py  ← Building block 6: safety
│   └── step7_react_agent.py      ← The complete agent
│
├── logs/                         ← Local log feeds (no CloudWatch needed)
│   ├── nginx/
│   │   ├── access.log            ← HTTP request log (with 502s)
│   │   └── error.log             ← Upstream connection failures
│   ├── app/
│   │   └── app.log               ← Application log (OOM crash here)
│   ├── database/
│   │   └── postgres.log          ← DB slow queries + max connections
│   └── kubernetes/
│       └── events.log            ← OOMKilling, BackOff, quota breach
│
├── tests/
│   └── test_all_steps.py         ← 26 tests, one for each building block
│
├── runbooks/
│   └── OOM_KILL_RECOVERY.md      ← Step-by-step human runbook
│
├── reports/                      ← Agent output goes here
│
├── docs/
│   └── THEORY_AND_REFERENCE.md   ← This file
│
└── README.md
```

**In a real production project, you would also add:**
```
├── .github/
│   └── workflows/
│       └── ci.yml               ← Run tests automatically on every code change
├── Dockerfile                   ← Package the agent as a container
├── requirements.txt             ← List of Python libraries
└── Makefile                     ← Shortcuts: make test, make run
```

---

## PART 5 — MAIN BLOCKERS IN LIVE IMPLEMENTATION

### Blocker 1: IAM / Permissions
The agent needs permission to read CloudWatch logs, Kubernetes events, database logs.
In most companies these permissions take weeks to get approved.

**What to do**: Create a dedicated service account (`sre-agent@company.com`) with least-privilege read-only access. Document exactly what permissions are needed and why.

### Blocker 2: Log Query Cost
CloudWatch Logs Insights charges per GB scanned. An agent making 8 queries per incident × 100GB logs = very expensive at scale.

**What to do**: Always query with a short time window (last 15 minutes). Use log level filters (only ERROR and above). Cache query results for 60 seconds to avoid repeated queries for the same incident.

### Blocker 3: Inconsistent Log Formats
Team A logs in JSON. Team B logs in plain text. Team C just changed their format last week.

**What to do**: Enforce a company-wide logging standard. Use a shared logging library that all teams import. Add a log format validator that runs in CI before a service deploys.

### Blocker 4: Organisational Trust
After one wrong RCA, people stop trusting the tool entirely.

**What to do**: Start by running the agent in "shadow mode" — it runs alongside the human investigation but its output is not shared until verified. Track accuracy. Build trust slowly before giving it authority.

### Blocker 5: The Agent Is Slow
Each tool call (CloudWatch query) takes 5-15 seconds. 8 iterations × 10 seconds = 80 seconds minimum. Too slow for a P0.

**What to do**: Make tool calls that don't depend on each other run in parallel. Pre-warm common queries. Cache results from the last 5 minutes.

### Blocker 6: PII in Logs
Postgres query logs contain real customer data. The agent reads this and puts it in the RCA.

**What to do**: Add a scrubbing layer between the log source and the agent. Replace emails, IPs, UUIDs with tokens before any log line reaches the agent.

---

## PART 6 — TIPS

### Tips for Understanding the Concepts

**The agent as a junior engineer on their first oncall shift**
The agent is like a junior engineer who has been given a checklist:
1. Check the app logs first
2. If you see OOM, check Kubernetes
3. Always check the database too
4. Count how many users were affected
5. Write up what you found

That's exactly what our `think()` function is — a checklist encoded in Python.

**THINK/ACT/OBSERVE is like the Scientific Method**
- THINK  = form a hypothesis ("I think the problem is X")
- ACT    = run an experiment ("let me check the logs to see")
- OBSERVE= analyse the result ("yes, OOM confirmed")
- Repeat

**Why MAX_ITERATIONS isn't just a safeguard — it's a design principle**
Bounding the agent forces you to think about what the MINIMUM necessary investigation looks like. If you need 20 iterations to form a conclusion, your tools are probably too granular.

**The guardrail is the most important part for SRE**
The technical community often gets excited about the agent loop. But for production SRE use, the guardrail is what makes the tool trustworthy. Without it, the agent is a liability, not an asset.

### Tips for Interviews

**Common question: "Can't you just feed all the logs to an LLM and ask it what went wrong?"**

Answer: Yes, for small log volumes. But:
1. Context window limits — 100GB of logs won't fit
2. Cost — feeding huge volumes to an LLM is expensive
3. Accuracy — an agent that SELECTS which logs to read based on findings is more focused than one that reads everything
4. Auditability — the ReAct trace shows exactly what was read and why

**Common question: "Why not just automate the fix?"**

Answer: We do — for safe, reversible actions with human approval (like restarting a deployment). But we never automate irreversible actions (like dropping a database or deleting volumes). The blast radius is too high. The agent produces a recommended fix list; a human or an approval workflow executes them.

**Common question: "How is this different from a monitoring alert?"**

Answer: An alert says "something is wrong". An SRE agent says "here is what went wrong, why it went wrong, how many users were affected, and here are the commands to fix it". The agent converts signal into action — alerts are still needed to trigger the agent.

---

## PART 7 — INTERVIEW QUESTIONS

### Conceptual Questions

**Q1: What is the ReAct pattern?**

ReAct is an agent architecture that interleaves reasoning and action in small cycles. Instead of planning everything upfront, the agent thinks about the next best step, takes that step, observes the result, and then thinks again. Each cycle produces a grounded decision based on real retrieved data. In SRE, this means each tool call is informed by what the previous call found — the agent adapts to the evidence rather than following a fixed script.

**Q2: What is hallucination, and why is it dangerous in SRE?**

Hallucination is when a model produces confident statements not supported by evidence. In SRE, a hallucinated RCA might say "DNS failure caused the outage" when no DNS issues appear in the logs. Engineers at 3am are tired and trust the tool — they spend hours debugging DNS while the real issue (OOM kill) goes unfixed. This worsens MTTR and destroys trust in the tool.

**Q3: How do you prevent hallucination without using another LLM?**

Use a citation-only RCA pattern with deterministic validation. Every claim in the RCA is checked against a corpus of actual log lines collected during the agent loop. We extract keywords from each claim and search the evidence. Claims with low evidence coverage are removed before the RCA is published. This is completely deterministic — no LLM call, no possibility of the guard itself hallucinating.

**Q4: Why do we set a MAX_ITERATIONS limit?**

Two reasons. First, safety: without it, a bug in the reasoning logic could cause an infinite loop that burns API credits and blocks incident response. Second, design: bounding iterations forces you to think about what the minimum necessary investigation is. If you need 20 iterations, your tools are too granular.

**Q5: What is the difference between planning and acting in an agent?**

Planning is reasoning about what to do — it has no real-world consequences and is cheap. Acting has real-world effects and may be irreversible. In SRE agents, planning (THINK) is free; acting (calling a tool) should be cautious. We only use read-only tools. Write operations (restart, patch, delete) are recommendations for humans, never automated actions.

### Technical Questions

**Q6: Walk me through what happens when the agent calls a tool.**

The `think()` function returns an action name (e.g., "read_app_logs"). The `run_tool()` function looks up that name in the `TOOLS` dictionary and calls the corresponding function. The function reads the log file and returns a list of lines. The `observe()` function processes those lines, extracts key findings, and adds them to the findings list. Those findings are passed to the next `think()` call.

**Q7: How does the hallucination guard's confidence score work?**

We define keyword groups for each type of claim (OOM, 502, database, kubernetes, etc.). For a given claim, we find which keyword groups match words in the claim text. Then we check how many of those groups also appear in the collected evidence. Confidence = matching groups / total relevant groups. If fewer than 50% of claim categories have supporting evidence, the claim is removed.

**Q8: Why do you have separate files for each step?**

Single responsibility principle. Each file does one thing and can be tested, replaced, or improved independently. If we want to improve the observe logic, we change `step5_observe.py` only — the agent loop doesn't change. If we want to add a new log source, we add a tool to `step3_tools.py` only. This is how production SRE tooling is maintained: modular, independently deployable.

**Q9: How would you add a new log source to this agent?**

Three changes: (1) Add a new function `tool_read_redis_logs()` to `step3_tools.py` and register it in `TOOLS`. (2) Add pattern matching for Redis keywords in `step5_observe.py`. (3) Add a reasoning branch in `step4_think.py` to decide when to call the new tool. Then write a test. Nothing else changes.

**Q10: How does this improve MTTR?**

MTTR = MTTD + MTTI + MTTF (detect + investigate + fix). The agent dramatically reduces MTTI — the investigation phase. In our scenario, a human takes 20 minutes to correlate 4 log sources. The agent does it in 5 iterations taking under 1 second each. If the investigation phase drops from 20 minutes to 1 minute, and the fix takes 10 minutes, MTTR goes from 35 minutes to 15 minutes. That is 60% less error budget consumed per incident.

### SRE-Specific Questions

**Q11: Where does this agent fit in the SRE error budget model?**

Faster MTTR = less downtime per incident = less error budget consumed per incident = more room to ship features without burning the budget. The agent makes the investigation phase nearly instant for known failure patterns. Over a month with 10 incidents, this could save 3+ hours of downtime — significant in a 99.9% SLO world where your monthly budget is 43 minutes.

**Q12: What SRE principles does this agent embody?**

Several: (1) Reducing toil — the most repetitive part of incident response (reading logs) is automated. (2) Eliminating variance — the agent gives the same quality RCA at 3am as at 3pm, and for a junior oncall as for a senior SRE. (3) Blameless culture — the agent produces evidence-based RCAs, not opinion-based ones, which makes postmortems less personal. (4) Error budget accountability — faster MTTR directly protects the SLO.

---

*End of Day 6 Theory & Reference Guide*

---

## QUICK REVISION TABLE

| Concept | One-line explanation |
|---------|---------------------|
| ReAct | Think a little → Act → See result → Repeat |
| Tool | A function the agent can call |
| THINK | Decide what to do next |
| ACT | Call the tool |
| OBSERVE | Extract key findings from tool output |
| MAX_ITERATIONS | Safety limit so the agent never runs forever |
| Hallucination | Agent says something confident that isn't in the logs |
| Guardrail | Checks every RCA claim against actual log evidence |
| Confidence score | 0.0 = no evidence, 1.0 = fully supported |
| Citation-only RCA | Every claim must link to a real log line |
| MTTR | Mean Time to Recover — what this tool improves |