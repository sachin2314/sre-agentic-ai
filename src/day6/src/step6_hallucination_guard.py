def check_claim_against_evidence(claim_text, evidence_lines):
    """
    Check if the claim is supported by the evidence we collected.
    claim_text = a sentence from our TCA, e.g. "OOM kill occurred at 08:00:55"
    evidence_lines = the list of key findings we collected during the ReAct loop
    Returns a dict with:
        "supported" = True or False
        "confidence" = a score from 0.0 to 1.0
        "reason" = why we gave this score
    """

    claim_keyword_groups = {
        "oom": ["oom", "out of memory", "137", "killed"],
        "502": ["502", "bad gateway", "upstream"],
        "database": ["connection", "postgres", "db", "database", "slow query"],
        "kubernetes": ["k8s", "pod", "quota", "backoff", "oomkilling"],
        "restart": ["restart", "attempt", "giving up", "failed container"],
    }

    all_evidence_text = "\n".join(evidence_lines).lower()
    claim_lower = claim_text.lower()
    
    relevant_groups = []

    for group_name, keywords in claim_keyword_groups.items():
        for keyword in keywords:
            if keyword in claim_lower:
                relevant_groups.append(group_name)
                break
    
    if not relevant_groups:
        return {
            "supported": False,
            "confidence": 0.0,
            "reason": "No recognisable claim keywords found -cannot verify"
        }
    
    supported_groups = 0
    for group_name in relevant_groups:
        keywords = claim_keyword_groups[group_name]
        for keyword in keywords:
            if keyword in all_evidence_text:
                supported_groups +=1
                break

    confidence = supported_groups / len(relevant_groups)
    supported = confidence >= 0.5

    return {
        "supported": supported,
        "confidence": round(confidence, 2),
        "reason": f"{supported_groups}/{len(relevant_groups)}"
    }


def validate_rca(rca_claims, evidence_lines):
    """
    Validate an entire list of RCA claims.
    Remove any that aren't supported by evidence.
    rca_claims = list of strings, each one a claim in the RCA
    evidence_lines = list of findings collected during the agent loop

    Returnds a dict with:
        "validated_claims" = only the claims that passed the check
        "removed_claims" = claims that were removed
        "report" = a summary of what happened
    """

    validated = []
    removed = []

    for claim in rca_claims:
        result = check_claim_against_evidence(claim, evidence_lines)

        if result["supported"]:
            validated.append(claim)
        else:
            removed.append({
                "claim": claim,
                "confidence": result["confidence"],
                "reason": result["reason"]
            })

    return{
        "validated_claims": validated,
        "removed_claims": removed,
        "total_checked": len(rca_claims),
        "total_validated": len(validated),
        "total_removed": len(removed)
    }



if __name__ == "__main__":
    print("========= STEP 6: Hallucination Guard =========")
    print()

    my_evidence = [
        "OOM KILL DETECTED: FATAL Process killed by OOM killer (exit code 137)",
        "DB CONNECTION FAILURE: ERROR Cannot connect to database: connection timeout",
        "DB EXHAUSTION: FATAL remaining connection slots are reserved - max connections hit",
        "POD RESTART: Warning BackOff Pod/app-pod-1 Back-off restarting failed container",
        "K8S QUOTA EXCEEDED: Warning FailedCreate pods is forbidden: exceeded quota pods=10/10",
        "IMPACT: 5 requests returned 502 Bad Gateway errors",
    ]

    rca_claims = [
        "The application was killed by the OOM killed at 08:01:55",
        "Database connections were exhausted preventing app restart",
        "5 requests received 502 Bad Gateway errors from nginx",
        "The incident was caused by a DNS misconfiguration in the VPC",
        "Kubernetes quota prevented new pods from starting",
    ]

    print("Evidence collected during agent loop:")
    for e in my_evidence:
        print(f" YES - {e}")

    print()
    print ("checking RCA claims against evidence...")
    print()

    result = validate_rca(rca_claims, my_evidence)

    print(f"RESULT: {result['total_validated']}/{result['total_checked']} claims passed the guard")
    print()

    print("YES Validated claims (will appear in RCA):")
    for claim in result["validated_claims"]:
        print(f" {claim}")
    print()

    if result["removed_claims"]:
        print("Nope REMOVED claims (not supported by evidence):")
        for item in result["removed_claims"]:
            print(f" Claim: {item['claim']}")
            print(f" Reason: {item['reason']}")
            print(f" Score: {item['confidence']}")
        