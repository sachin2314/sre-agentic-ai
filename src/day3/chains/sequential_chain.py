from langchain_core.prompts import ChatPromptTemplate
from langchain_aws import ChatBedrockConverse
import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

model = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID"),
    region_name=os.getenv("AWS_REGION")
)

summary_prompt = ChatPromptTemplate.from_messages([
    ("system", "Summarise the logs"),
    ("user", "{logs}.")
])

analyse_prompt = ChatPromptTemplate.from_messages([
    ("system", "Analyse the summary with root_cause, severity, recommended_fix."),
    ("user", "{summary}.")
])

summarise_chain = summary_prompt | model
analyse_chain = analyse_prompt | model

full_chain = {"summary" : summarise_chain} | analyse_chain

logs = open("src/day2/sample_logs/logs.txt", "r").read()    

response = full_chain.invoke({"logs": logs}).content
print(response)

