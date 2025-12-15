"""
Create Vector Database for US Code
Embeds all sections for semantic search using OpenAI text-embedding-3-large

Performance improvements:
- Increased batch size (500 vs 100) for faster indexing
- Uses config module for centralized settings
- Proper logging instead of print statements
"""

import logging
import time
import sys
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from tqdm import tqdm

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.processing.parse_uscode import parse_uscode_xml, USING_LXML

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Try to use config, fall back to env vars
try:
    from app.config import get_settings

    settings = get_settings()
    DATA_DIR = settings.data_dir
    USCODE_DIR = settings.uscode_dir
    VECTOR_DB_DIR = settings.vector_db_dir
    OPENAI_API_KEY = settings.openai_api_key
    EMBEDDING_MODEL = settings.embedding_model
    BATCH_SIZE = settings.vector_batch_size
except ImportError:
    import os
    from dotenv import load_dotenv

    load_dotenv()
    DATA_DIR = PROJECT_ROOT / "data"
    USCODE_DIR = DATA_DIR / "uscode"
    VECTOR_DB_DIR = DATA_DIR / "vector_db"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    EMBEDDING_MODEL = "text-embedding-3-large"
    BATCH_SIZE = 500  # Increased from 100


def create_vector_database():
    """Create ChromaDB vector database from all US Code sections"""

    logger.info("=" * 60)
    logger.info("CREATING VECTOR DATABASE FOR US CODE")
    logger.info(f"Using {EMBEDDING_MODEL}")
    logger.info(f"XML Parser: {'lxml (fast)' if USING_LXML else 'stdlib'}")
    logger.info(f"Batch size: {BATCH_SIZE}")
    logger.info("=" * 60)

    # Get OpenAI API key
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not found in environment")
        logger.info("Add to .env file or set environment variable")
        return False

    # Initialize ChromaDB with persistent storage
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))

    # Create OpenAI embedding function
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY, model_name=EMBEDDING_MODEL
    )

    # Create or get collection
    try:
        client.delete_collection("uscode")
        logger.info("Deleted existing collection")
    except Exception:
        pass

    collection = client.create_collection(
        name="uscode",
        embedding_function=openai_ef,
        metadata={
            "description": "US Code sections for semantic search",
            "model": EMBEDDING_MODEL,
        },
    )

    logger.info("Scanning for US Code XML files...")

    # Find all XML files
    xml_files = list(USCODE_DIR.rglob("*.xml"))
    logger.info(f"Found {len(xml_files)} XML files")

    if not xml_files:
        logger.error("No XML files found!")
        logger.info("Run: python scripts/download/download_full_code.py")
        return False

    # Process all sections
    all_sections = []
    logger.info("Parsing XML files...")

    for xml_file in tqdm(xml_files, desc="Parsing titles"):
        try:
            sections = parse_uscode_xml(xml_file)
            all_sections.extend(sections)
        except Exception as e:
            logger.warning(f"Error parsing {xml_file.name}: {e}")
            continue

    logger.info(f"Parsed {len(all_sections)} total sections")

    if not all_sections:
        logger.error("No sections found!")
        return False

    # Prepare data for ChromaDB
    logger.info("Preparing documents for embedding...")

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

    # Add to ChromaDB in batches
    logger.info(f"Embedding {len(documents)} sections (batch size: {BATCH_SIZE})...")
    logger.info("Estimated cost: ~$3-5 in OpenAI API credits")

    for i in tqdm(range(0, len(documents), BATCH_SIZE), desc="Adding batches"):
        batch_docs = documents[i : i + BATCH_SIZE]
        batch_meta = metadatas[i : i + BATCH_SIZE]
        batch_ids = ids[i : i + BATCH_SIZE]

        try:
            collection.add(documents=batch_docs, metadatas=batch_meta, ids=batch_ids)
        except Exception as e:
            logger.error(f"Error adding batch {i}: {e}")
            continue

    logger.info("=" * 60)
    logger.info("VECTOR DATABASE CREATED SUCCESSFULLY")
    logger.info("=" * 60)
    logger.info(f"Location: {VECTOR_DB_DIR}")
    logger.info(f"Sections indexed: {len(documents)}")

    return True


def test_search():
    """Test the vector database with a sample query"""
    logger.info("=" * 60)
    logger.info("TESTING VECTOR DATABASE")
    logger.info("=" * 60)

    client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
    collection = client.get_collection("uscode")

    test_queries = [
        "copyright protection and duration",
        "criminal penalties for fraud",
        "tax deductions for businesses",
    ]

    for query in test_queries:
        logger.info(f"Query: '{query}'")
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
