from langchain_aws import ChatBedrockConverse
import os  
import sys
from dotenv import load_dotenv
from src.day2.prompts.sre_prompts import safety_prompt

def prompt_implementation(prompt, logs):
    sys.stdout.reconfigure(encoding='utf-8')
    load_dotenv()

    model = ChatBedrockConverse(
        model=os.getenv("BEDROCK_MODEL_ID"),
        region_name=os.getenv("AWS_REGION")
    )
    chain = prompt | model
    response = chain.invoke({"logs": logs}).content
    return response
