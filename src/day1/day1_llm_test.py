from langchain_aws import ChatBedrockConverse
import os
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

model = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID"),
    region_name=os.getenv("AWS_REGION")
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert SRE assistant"),
    ("user", "Explain what an LLM is in simple terms")
])

chain = prompt | model

response = chain.invoke({})
print(response.content)
