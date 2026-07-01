import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.stdout.reconfigure(encoding='utf-8')
from src.day5.rag.load_and_chunk import load_runbook_document, chunk_documents
from src.day5.rag.embeddings_and_store import build_vector_store_from_docs
from src.day5.rag.embeddings_and_store import build_embeddings_model
from src.day5.rag.retriever import build_retriever
from src.day5.rag.embeddings_and_store import build_vector_store_from_docs
from src.day5.rag.rag_chain import run_rag_query

def main():
    # Step 1: Load and chunk runbook documents
    docs = load_runbook_document("runbooks")
    chunked_docs = chunk_documents(docs)

    # Step 2: Build vector store from chunked documents
    vector_store = build_vector_store_from_docs(chunked_docs)

    # Step 3: Build retriever
    retriever = build_retriever(vector_store)

    # Step 4: Run a RAG query
    queries = [
        "How do we handle EKS CrashLoopBackOff for the file-upload service?",
        "What is the standard process for investigating Lambda timeouts?",
    ]
    
    for q in queries:
        print("=" * 80)
        print(f"QUESTION: {q} \n")
        answer = run_rag_query(retriever, q)
        print("ANSWER:")
        print(answer)
        print("=" * 80)
        print()

if __name__ == "__main__":
    main()


