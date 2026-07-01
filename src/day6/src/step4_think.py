def think(tools_already_used, findings_so_far):
    """
    Decide what the next action should be.
    tools_already_used = a list of tool names we have arleady called 
    findings_so_far = a list of findings we have already collected
                        e.g. ["read_app_logs", "count_502_errors"]
    return a dict with:
        "thought" = the reasoning text (WHY we picked this action)
        "action" = the tool name to call next (or "FINISH")
    """

    if "read_app_logs" not in tools_already_used:
        return {
            "thought": (
                " I have not read any logs yet."
                "I will start with the application log because that is where"
                "crash error and memory problems will appear first"
            ),
            "action": "read_app_logs"
        }
    
    oom_found = any("oom" in finding.lower() or "137" in finding or "fatal" in finding.lower()
                    for finding in findings_so_far)
    
    
    if oom_found and "read_k8s_logs" not in tools_already_used:
        return {
            "thought": (
                "The application log shows an OOM kill or fatal error."
                "I need to check kubernetes events to confirm the OOMKilling"
                "and see if pods restarted successfully"
            ),
            "action": "read_k8s_logs"
        }
    
    if "count_502_errors" not in tools_already_used:
        return {
            "thought": (
                "I should count the 502 HTTP errors in the nginx access logs"
                "to understand how many users were affected."
            ),
            "action": "count_502_errors"
        }
    
    if "read_db_logs" not in tools_already_used:
        return {
            "thought": (
                "Now I will check the database logs."
                "The app failed to reconnect to the database on restart - "
                "I need to know if the DB itself had problems (like too many connections)."
            ),
            "action": "read_db_logs"
        }
    
    return {
        "thought": (
            "I have now checked the application logs, kubernetes events,"
            "nginx 502 count, and database log."
            "I have enough evidence to write the root cause analysis."
        ),
        "action": "FINISH"
    }

if __name__ == "__main__":
    print("========= STEP 4: The Think Step =========")
    print()

    #Simulate the think step at different stages

    #Stage 1: Nothing done yet
    print("Situation: Agent just started, nothing done yet")
    result = think(tools_already_used=[], findings_so_far=[])
    print(f"Thought: {result['thought']}")
    print(f"Action: {result['action']}")
    print()

    #Stage 2: App logs was read, found OOM
    print("Situation: App logs read, found OOM error --")
    result = think(
        tools_already_used=["read_app_logs"], 
        findings_so_far=["Found OOM kill at 08:01:55 - exit code 137"]
        )

    print(f"Thought: {result['thought']}")
    print(f"Action: {result['action']}")
    print()

    print("-- Situation: App + K8s read, now checking 502s --")
    result = think(
        tools_already_used=["read_app_logs", "read_k8s_logs"], 
        findings_so_far=["OOMKilling confirmed in k8s events"]
        )

    print(f"Thought: {result['thought']}")
    print(f"Action: {result['action']}")
    print()

    #Stage 4: All done
    print("-- Situation: All important logs read --")
    result = think(
        tools_already_used = ["read_app_logs", "read_k8s_logs", "count_502_errors", "read_db_logs"],
        findings_so_far = ["OOM found", "5 x 502 errors", "DB connections exhausted"]
    )
    print(f"Thought: {result['thought']}")
    print(f"Action: {result['action']}")

    

