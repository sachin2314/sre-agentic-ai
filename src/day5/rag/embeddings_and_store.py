import os
from typing import List
from dotenv import load_dotenv
from langchain_aws import BedrockEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

load_dotenv()


def build_embeddings_model():
    """Build and return the embeddings model."""
    return BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v2:0",
        region_name=os.getenv("AWS_REGION")
    )


def build_vector_store_from_docs(docs: List[Document]) -> FAISS:
    """Build a FAISS vector store from a list of documents."""
    embeddings = build_embeddings_model()
    return FAISS.from_documents(docs, embeddings)
