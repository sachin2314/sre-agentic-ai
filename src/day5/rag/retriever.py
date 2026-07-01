from langchain_community.vectorstores import FAISS


def build_retriever(vector_store: FAISS, k: int = 4):
    """Build a retriever from a FAISS vector store."""
    return vector_store.as_retriever(search_kwargs={"k": k})
