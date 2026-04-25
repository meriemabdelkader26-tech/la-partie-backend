import json
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

# Credentials
QDRANT_URL = "https://73b0fb86-a6a8-45eb-8e70-cc1697987b8a.eu-central-1-0.aws.cloud.qdrant.io:6333"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6MTU5NTBjZDMtNTUxNy00Y2Q0LTlmNDMtZjgzNzBlNDhkY2ZiIn0.n1xPzYsMFfvbcjFVJdjPuNENFLLjM5tET0-Yr7n9RTw"
COLLECTION_NAME = "influbridge_faq"

def index_data():
    # Load data
    with open('users/rag_data.json', 'r') as f:
        data = json.load(f)

    # Initialize embeddings
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Initialize Qdrant client
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # Recreate collection (optional, but good for fresh start)
    # Be careful in production!
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if exists:
        print(f"Collection {COLLECTION_NAME} already exists. Deleting and recreating...")
        client.delete_collection(collection_name=COLLECTION_NAME)
    
    print(f"Creating collection {COLLECTION_NAME}...")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    )
    
    # Add payload index for 'actor' to allow filtering
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="actor",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )

    # Index data
    documents = []
    metadatas = []
    ids = []

    for i, item in enumerate(data):
        text = f"Question: {item['question']}\nAnswer: {item['answer']}"
        documents.append(text)
        metadatas.append({
            "actor": item["actor"],
            "question": item["question"],
            "answer": item["answer"]
        })
        ids.append(i)

    # Use LangChain's Qdrant integration to index
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings,
    )

    vector_store.add_texts(texts=documents, metadatas=metadatas)
    print("Indexing complete!")

if __name__ == "__main__":
    index_data()
