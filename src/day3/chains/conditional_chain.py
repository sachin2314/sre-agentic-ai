from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnableBranch
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

short_prompt = ChatPromptTemplate.from_messages([
    ("system", "Summarise the logs brefily"),
    ("user", "{logs}.")
])

long_prompt = ChatPromptTemplate.from_messages([
    ("system", "Summarise the logs in details"),
    ("user", "{logs}.")
])


runnable_branch = RunnableBranch(
    lambda inputs: short_prompt | model if len(inputs["logs"]) < 1 else long_prompt | model
)

runnable_branch = RunnableBranch(
    (lambda inputs: len(inputs["logs"]) < 1000, short_prompt | model),
    long_prompt | model
)

logs = open("src/day2/sample_logs/logs.txt", "r").read()    

response = runnable_branch.invoke({"logs": logs}).content
print(response)

