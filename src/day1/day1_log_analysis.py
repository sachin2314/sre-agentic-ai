from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate
import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

with open("logs.txt", "r") as f:
    logs = f.read()


model = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID"),
    region_name=os.getenv("AWS_REGION")
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert SRE assistant"),
    ("user", "Analyze the following logs and identify any potential issues:\n\n{logs}")
])

chain = prompt | model
response = chain.invoke({"logs": logs})
print(response.content)
print(response)
tokens_used = response.usage_metadata["input_tokens"]
output_tokens = response.usage_metadata["output_tokens"]
print(f"Tokens used — input: {tokens_used}, output: {output_tokens}, total: {response.usage_metadata['total_tokens']}")

