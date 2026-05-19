from langchain_core.prompts import ChatPromptTemplate
from langchain_aws import ChatBedrockConverse
import os  
import sys
from dotenv import load_dotenv
from src.day2.prompts.sre_prompts import safety_prompt

def safety_prompt_analysis(safety_prompt):
    sys.stdout.reconfigure(encoding='utf-8')
    load_dotenv()

    model = ChatBedrockConverse(
        model=os.getenv("BEDROCK_MODEL_ID"),
        region_name=os.getenv("AWS_REGION")
    )

    logs = open("src/day2/sample_logs/logs.txt", "r").read()

    chain = safety_prompt | model
    response = chain.invoke({"logs": logs}).content
    #print(response)
    return response
