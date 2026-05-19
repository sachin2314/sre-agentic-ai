from day2_prompt_evaluator import evaluate_response
from src.day2.prompts.sre_prompts import safety_prompt, kubernetes_prompt, log_analysis_prompt
from src.day2.prompts.day2_prompt_application import prompt_implementation
import sys

sys.stdout.reconfigure(encoding='utf-8')


# prompt = """
# Analyse logs and return JSON with root_cause, severity, recommended_fix.
# """

# answer = """
# {
#   "root_cause": "Missing module 'requests'",
#   "severity": "medium",
#   "recommended_fix": "Add requests to requirements.txt"
# }
# """




print(evaluate_response(safety_prompt, prompt_implementation(safety_prompt, open("src/day2/sample_logs/logs.txt", "r").read())))
print(evaluate_response(kubernetes_prompt, prompt_implementation(kubernetes_prompt, open("src/day2/sample_logs/logs.txt", "r").read())))
print(evaluate_response(log_analysis_prompt, prompt_implementation(log_analysis_prompt, open("src/day2/sample_logs/logs.txt", "r").read())))







