import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


from src.day6.src.step3_tools import run_tool
from src.day6.src.step4_think import think
from src.day6.src.step5_observe import observe
from src.day6.src.step6_hallucination_guard import validate_rca
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

model = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID"),
    region_name=os.getenv("AWS_REGION")
)


def run_react_agent():
    """
    Run the full ReAct agent loop.
    Returns the final validated RCA (Root Cause Analysis).
    """
    print("=" *55)
    print(" SRE AGENT STARTING")
    print("=" * 55)
    print()

    tools_used = []
    findings = []
    all_evidence = []
    trace = []
    MAX_ITERATIONS = 10
    iteration = 0

    while iteration < MAX_ITERATIONS:
        iteration += 1
        print(f"--- Iteration {iteration} ----")
        think_result = think(
            tools_already_used=tools_used,
            findings_so_far=findings
        )

        thought = think_result["thought"]
        action = think_result["action"]
        
        print(f"THOUGHT: {thought}")
        print(f"ACTION: {action}")


        if action == "FINISH":
            print()
            print("Agent decided to finish the investigation.")
            break

        raw_output = run_tool(action)
        new_findings = observe(action, raw_output)
        findings.extend(new_findings)

        if isinstance(raw_output, list):
            all_evidence.extend(raw_output)

        print(f"Observe: Found {len(new_findings)} new findings.")
        for f in new_findings:
            print(f" >> {f}")

        tools_used.append(action)

        trace.append({
            "iteration": iteration,
            "thought": thought,
            "action": action,
            "findings": new_findings,
        })

    print()
    #PRODUCE THE RCA
    print()
    print("=" *55)
    print(" PRODUCING ROOT CAUSE ANALYSIS")
    print("=" * 55)
    print()

    rca = build_rca(findings)

    print("Running hallucination guard....")

    guard_result = validate_rca(rca["claims"], findings)

    print(f"Guard result: {guard_result['total_validated']}/{guard_result['total_checked']} claims passed")

    if guard_result["removed_claims"]:
        print("Removed unsupported claims:")
        for item in guard_result["removed_claims"]:
            print(f" X {item['claim'][:60]}...")

    print()    

    rca["claims"] = guard_result["validated_claims"]
    rca["guard_report"] = guard_result
    rca["react_trace"] = trace
    rca["iterations_taken"] = iteration

    return rca

def build_rca(findings):
    """
    Send all agent findings to the LLM and ask it to produce a structured Root Cause Analysis.
    Returns a dict with:
        severity, summary, root_cause, claims, fixes
    """
    findings_block = "\n".join(f"- {f})" for f in findings)
    system_prompt = (
        "You are a senior Site Reliability Engineer (SRE) writing a formal"
        "Post-Incident Root Cause Analysis (RCA)."
        "Be concise, precise, and stick strictly to the evidence provided."
        "Do NOT invent factsthat are not supported by the findings."
        )

    user_prompt = f"""
    Based on the following evidence gathered during an incident investigation, produce a structured RCA.
    FINDINGS:
    {findings_block}
    Reply in EXACTLY this format (keep the section headers verbatim):
    SEVERITY: <P1/P2/P3 and one-line description>>
    SUMMARY: <2-4 sentences describing what happened end-to-end>
    ROOT_CAUSE: < single most important cause in 1-2 sentences>
    CLAIMS:
    - <claim 1 that is directly supported by the findings>
    - <claim 2 >
    - <... add as many as the evidence supports>
    FIXES:
    -<concrete remediation command or action>
    -<...>
    """

    response = model.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])

    raw_text = response.content
    return _parse_llm_rca(raw_text)

def _parse_llm_rca(text: str)-> str:
    """
    Parse the LLM's free-texct RCA reploy into the dict strcuture
    the rest of the agent expects.
    """

    result = {
        "severity": "",
        "summary": "",
        "root_cause": "",
        "claims": [],
        "fixes": []
    }

    section = None

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("SEVERITY:"):
            result["severity"] = stripped[len("SEVERITY:"):].strip()
            section = None

        elif stripped.startswith("SUMMARY:"):
            result["summary"] = stripped[len("SUMMARY:"):].strip()
            section = "summary"

        elif stripped.startswith("ROOT_CAUSE:"):
            result["root_cause"] = stripped[len("ROOT_CAUSE:"):].strip()
            section = "root_cause"

        elif stripped == "CLAIMS:":
            section = "claims"

        elif stripped == "FIXES:":
            section = "fixes"

        elif stripped.startswith("- ") and section in ("claims", "fixes"):
            result[section].append(stripped[2:].strip())

        elif stripped and section in ("summary", "root_cause"):
            result[section] += " " + stripped


    return result

def print_rca(rca: dict) -> None:
    """
    Print the RCA in a readable format.
    """

    print("=" * 55)
    print(" FINAL ROOT CAUSE ANALYSIS")
    print("=" * 55)
    print()
    print(f"SEVERITY: {rca['severity']}")
    print()
    print(f"SUMMARY")
    print(f" {rca['root_cause']}")
    print()
    print("VALIDATED CLAIMS:")
    for claim in rca["claims"]:
        print(f" YES {claim}")

    print()
    print("IMMEDIATE FIXES")
    for fix in rca["fixes"]:
        print(f" -> {fix}")
    
    print()
    print(f"Agent took {rca['iterations_taken']}  iterations")
    print(f"Guard removed {rca['guard_report']['total_removed']}  unsupported claim(s)")


if __name__ == "__main__":
    rca = run_react_agent()
    print_rca(rca)
    




    
