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

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a senior SRE expert. Be precise and factual"),
    ("user", "Explain the difference between CPU saturation and CPU throttling in simple terms")
])

chain = prompt | model
response = chain.invoke({}).content
print(response)
