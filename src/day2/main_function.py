import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.day2.prompts.day2_prompt_application import prompt_implementation
from src.day2.prompts.sre_prompts import safety_prompt, kubernetes_prompt, log_analysis_prompt

print(prompt_implementation(safety_prompt, open("src/day2/sample_logs/logs.txt", "r").read()))
print(prompt_implementation(kubernetes_prompt, open("src/day2/sample_logs/logs.txt", "r").read()))
print(prompt_implementation(log_analysis_prompt, open("src/day2/sample_logs/logs.txt", "r").read()))