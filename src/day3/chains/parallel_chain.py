from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel
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

severity_prompt = ChatPromptTemplate.from_messages([
    ("system", "Rate severity from 1-5"),
    ("user", "{logs}.")
])

# summarise_chain = summary_prompt | model
# severity_chain = severity_prompt | model

full_chain = RunnableParallel({
                "summary" : summary_prompt | model, 
                "severity": severity_prompt | model
            })

logs = open("src/day2/sample_logs/logs.txt", "r").read()    

response_whole = full_chain.invoke({"logs": logs})
response = full_chain.invoke({"logs": logs})["summary"].content
print(response)

