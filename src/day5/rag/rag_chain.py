import os
from typing import List
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_aws import ChatBedrockConverse

load_dotenv()

RAG_SYSTEM_PROMPT = """
You are an SRE assistant for a production system.

You are given:
- A user question about incidents, outages, or SRE procedures.
- A set of runbook and knowledge base snippets as context.

Your job:
- Answer the question using ONLY the provided context.
- If the context is insufficient, say so explicitly and suggest what additional information is needed.
- Prefer quoting or paraphrasing relevant parts of the context.
- Do NOT invent procedures or steps that are not supported by the context.

Answer clearly and concisely, but with enough detail to be actionable.
"""


def build_rag_llm():
    return ChatBedrockConverse(
        model=os.getenv("BEDROCK_MODEL_ID"),
        region_name=os.getenv("AWS_REGION")
    )


def format_context(docs: List[Document]) -> str:
    """Format retrieved documents into a context string for the LLM."""
    parts = []
    for i, d in enumerate(docs, start=1):
        source = d.metadata.get("source", "unknown")
        parts.append(f"[{i}] Source: {source}\n{d.page_content}\n")
    return "\n".join(parts)


def run_rag_query(retriever, query: str) -> str:
    """Retrieve relevant docs and run the query through the LLM."""
    docs: List[Document] = retriever.invoke(query)
    context_text = format_context(docs)

    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_SYSTEM_PROMPT),
        ("human", "Context:\n{context}\n\nQuestion:\n{question}"),
    ])

    llm = build_rag_llm()
    chain = prompt | llm
    response = chain.invoke({"context": context_text, "question": query})
    return response.content
