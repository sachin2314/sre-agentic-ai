from langchain_aws import ChatBedrockConverse
import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.day2.prompts.sre_prompts import evaluate_prompt

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

model = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID"),
    region_name=os.getenv("AWS_REGION")
)

def evaluate_response(prompt, answer):
    chain = evaluate_prompt | model
    response = chain.invoke({"prompt": prompt, "answer": answer}).content
    print(response)
    return response