import os
from typing import List
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def load_runbook_document(path: str) -> List[Document]:
    """Load runbook documents from a folder path."""
    docs: List[Document] = []

    for filename in os.listdir(path):
        if filename.endswith((".txt", ".md")):
            full_path = os.path.join(path, filename)
            loader = TextLoader(full_path, encoding="utf-8")
            file_docs = loader.load()

            for d in file_docs:
                d.metadata["source"] = filename

            docs.extend(file_docs)

    return docs


def chunk_documents(docs: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
    """Chunk documents into smaller pieces for better retrieval."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len
    )
    return splitter.split_documents(docs)
