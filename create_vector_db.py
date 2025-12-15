"""
Create Vector Database for US Code
Embeds all sections for semantic search using OpenAI text-embedding-3-large
"""

import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
from tqdm import tqdm
from parse_uscode import parse_uscode_xml
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Directories
DATA_DIR = Path(__file__).parent / "data"
USCODE_DIR = DATA_DIR / "uscode"
VECTOR_DB_DIR = DATA_DIR / "vector_db"


def create_vector_database():
    """Create ChromaDB vector database from all US Code sections"""

    print("=" * 70)
    print("CREATING VECTOR DATABASE FOR US CODE")
    print("Using OpenAI text-embedding-3-large")
    print("=" * 70)

    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n❌ OPENAI_API_KEY not found in environment")
        print("Add to .env file or set environment variable:")
        print("  export OPENAI_API_KEY='your-key-here'")
        return

    # Initialize ChromaDB with persistent storage
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))

    # Create OpenAI embedding function
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key, model_name="text-embedding-3-large"
    )

    # Create or get collection
    try:
        client.delete_collection("uscode")
    except:
        pass

    collection = client.create_collection(
        name="uscode",
        embedding_function=openai_ef,
        metadata={
            "description": "US Code sections for semantic search",
            "model": "text-embedding-3-large",
        },
    )

    print("\nScanning for US Code XML files...")

    # Find all XML files
    xml_files = list(USCODE_DIR.rglob("*.xml"))
    print(f"Found {len(xml_files)} XML files across {len(xml_files)} titles")

    if not xml_files:
        print("\n❌ No XML files found!")
        print("Run: python download_full_code.py")
        return

    # Process all sections
    all_sections = []
    print("\nParsing XML files...")

    for xml_file in tqdm(xml_files, desc="Parsing titles"):
        try:
            sections = parse_uscode_xml(xml_file)
            all_sections.extend(sections)
        except Exception as e:
            print(f"\n  Error parsing {xml_file.name}: {e}")
            continue

    print(f"\n✓ Parsed {len(all_sections)} total sections")

    if not all_sections:
        print("❌ No sections found!")
        return

    # Prepare data for ChromaDB
    print("\nPreparing documents for embedding...")

    documents = []
    metadatas = []
    ids = []

    for idx, section in enumerate(all_sections):
        # Create document text (combine identifier, heading, and text)
        doc_text = f"{section.identifier}: {section.heading}\n\n{section.text}"

        # Truncate very long sections (embedding models have token limits)
        if len(doc_text) > 8000:
            doc_text = doc_text[:8000] + "..."

        documents.append(doc_text)
        metadatas.append(
            {
                "identifier": section.identifier,
                "heading": section.heading,
                "text_length": len(section.text),
            }
        )
        ids.append(f"section_{idx}")

    # Add to ChromaDB in batches (ChromaDB has batch size limits)
    print(f"\nEmbedding and storing {len(documents)} sections...")
    print("Using OpenAI API - this will cost approximately $3-5")
    print("Estimated time: 15-30 minutes (depends on API rate limits)...")

    batch_size = 100
    for i in tqdm(range(0, len(documents), batch_size), desc="Adding batches"):
        batch_docs = documents[i : i + batch_size]
        batch_meta = metadatas[i : i + batch_size]
        batch_ids = ids[i : i + batch_size]

        try:
            collection.add(documents=batch_docs, metadatas=batch_meta, ids=batch_ids)
        except Exception as e:
            print(f"\n  Error adding batch {i}: {e}")
            continue

    print("\n" + "=" * 70)
    print("✓ VECTOR DATABASE CREATED SUCCESSFULLY")
    print("=" * 70)
    print(f"\nLocation: {VECTOR_DB_DIR}")
    print(f"Sections indexed: {len(documents)}")
    print(f"\nYou can now search semantically across the entire US Code!")
    print("Try: python search_code.py 'what are the rules about copyright'")


def test_search():
    """Test the vector database with a sample query"""
    print("\n" + "=" * 70)
    print("TESTING VECTOR DATABASE")
    print("=" * 70)

    client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
    collection = client.get_collection("uscode")

    test_queries = [
        "copyright protection and duration",
        "criminal penalties for fraud",
        "tax deductions for businesses",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = collection.query(query_texts=[query], n_results=3)

        print("\nTop 3 results:")
        for i, (doc, meta) in enumerate(
            zip(results["documents"][0], results["metadatas"][0])
        ):
            print(f"\n{i+1}. {meta['identifier']}: {meta['heading']}")
            print(f"   Preview: {doc[:200]}...")


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        test_search()
    else:
        print("\n⚠️  This will create embeddings for all US Code sections")
        print("   Requirements:")
        print("   - pip install chromadb openai python-dotenv")
        print("   - OpenAI API key in .env file")
        print("   - All US Code titles downloaded")
        print("   - Cost: ~$3-5 in OpenAI API credits")
        print("   - Time: ~15-30 minutes")
        print("   - Storage: ~500MB disk space for vector database")

        response = input("\nContinue? (yes/no): ")
        if response.lower() == "yes":
            start = time.time()
            create_vector_database()
            elapsed = time.time() - start
            print(f"\nCompleted in {elapsed/60:.1f} minutes")

            # Test it
            test_response = input("\nRun test search? (yes/no): ")
            if test_response.lower() == "yes":
                test_search()
        else:
            print("Cancelled.")
