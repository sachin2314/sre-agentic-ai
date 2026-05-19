from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate
import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

model = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID"), 
    region_name=os.getenv("AWS_REGION")
)  

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a senior SRE log analysis expert. Output ONLY valid JSON."),
    ("user", """
     Analyse the following logs and return JSON with:
     {{
     "root_cause": "",
     "severity": "",
     "recommended_fix": ""
     }}
     Logs:
     {logs}
     """)
])

logs = open("src/day2/sample_logs/logs.txt", "r").read()

chain = prompt | model
response = chain.invoke({"logs": logs}).content 
print(response)