from langchain_aws import ChatBedrockConverse
import os
import sys
import json
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.day2.prompts.sre_prompts import log_analysis_prompt, safety_prompt, evaluate_prompt

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

model = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID"),
    region_name=os.getenv("AWS_REGION")
)

logs = open("src/day2/sample_logs/logs.txt", "r").read()

prompts_to_compare = {
    "Basic Prompt":  log_analysis_prompt,
    "Safety Prompt": safety_prompt,
}

evaluation_results = {}

for name, prompt in prompts_to_compare.items():
    print(f"\n{'='*60}")
    print(f"  Running: {name}")
    print(f"{'='*60}")

    # Step 1 — get model answer
    answer = (prompt | model).invoke({"logs": logs}).content
    print(f"Answer:\n{answer}")

    # Step 2 — evaluate the answer
    print(f"\n  Evaluating {name}...")
    eval_response = (evaluate_prompt | model).invoke({
        "prompt": prompt.format(logs=logs),
        "answer": answer
    }).content

    print(f"Evaluation:\n{eval_response}")

    try:
        clean = eval_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        scores = json.loads(clean)
    except json.JSONDecodeError:
        scores = {"error": "Could not parse evaluation JSON"}

    evaluation_results[name] = scores

# Final scoreboard
print(f"\n{'='*60}")
print("  EVALUATION SCOREBOARD")
print(f"{'='*60}")
print(f"{'Metric':<15}", end="")
for name in evaluation_results:
    print(f"{name:<20}", end="")
print()
print("-" * 60)

metrics = ["clarity", "correctness", "grounding", "safety"]
for metric in metrics:
    print(f"{metric:<15}", end="")
    for name, scores in evaluation_results.items():
        val = scores.get(metric, "N/A")
        print(f"{str(val):<20}", end="")
    print()

print("-" * 60)
print(f"{'comments':<15}", end="")
for name, scores in evaluation_results.items():
    comment = scores.get("comments", "")[:40]
    print(f"{comment:<40}", end="")
print()