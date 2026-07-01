from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_aws import ChatBedrockConverse
import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

class RCA(BaseModel):
    root_cause: str = Field(..., description="Root cause")
    severity: str = Field(..., description="Severity level")
    fix: str = Field(..., description="Recommended fix")

parser = PydanticOutputParser(pydantic_object=RCA)

model = ChatBedrockConverse(
    model=os.getenv("BEDROCK_MODEL_ID"),
    region_name=os.getenv("AWS_REGION")
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "Output valid JSON matching this schema:\n{format_instructions}"),
    ("user", "Analyse: Lambda failed due to missing module.")
]).partial(format_instructions=parser.get_format_instructions())

chain = prompt | model | parser
response = chain.invoke({})
print(response)