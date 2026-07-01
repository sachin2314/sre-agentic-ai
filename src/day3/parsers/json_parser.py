from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_aws import ChatBedrockConverse
import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

parser = JsonOutputParser()

model = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID"),
    region_name=os.getenv("AWS_REGION")
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a senior SRE expert. Be precise and factual"),
    ("user", 'Return {{"status": "ok", "reason": "test"}}')
])

chain = prompt | model | parser
response = chain.invoke({})
print(response)