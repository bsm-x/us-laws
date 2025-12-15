"""Test creating a simple vector database with just a few documents"""

import chromadb
from chromadb.utils import embedding_functions
import os
from dotenv import load_dotenv

load_dotenv()

print("Starting simple test...")

# Get API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("ERROR: No API key found")
    exit(1)

print("API key found")

# Create client
client = chromadb.PersistentClient(path="data/vector_db_test")
print("Client created")

# Create embedding function
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=api_key, model_name="text-embedding-3-large"
)
print("Embedding function created")

# Delete existing collection if any
try:
    client.delete_collection("test")
except:
    pass

# Create collection
collection = client.create_collection(name="test", embedding_function=openai_ef)
print("Collection created")

# Add first batch
print("Adding batch 1...")
try:
    collection.add(
        documents=["Test document 1", "Test document 2"],
        metadatas=[{"id": "1"}, {"id": "2"}],
        ids=["doc1", "doc2"],
    )
    print("Batch 1 added successfully")
except Exception as e:
    print(f"ERROR adding batch 1: {type(e).__name__}: {e}")
    import traceback

    traceback.print_exc()
    exit(1)

# Add second batch
print("Adding batch 2...")
collection.add(
    documents=["Test document 3", "Test document 4"],
    metadatas=[{"id": "3"}, {"id": "4"}],
    ids=["doc3", "doc4"],
)
print("Batch 2 added successfully")

# Check count
count = collection.count()
print(f"Total documents: {count}")

print("Test completed successfully!")
