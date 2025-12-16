"""
Add Supreme Court Opinions to Vector Database
Reads from the SQLite database created by download_scotus_opinions.py
and adds opinion embeddings to the LanceDB vector database.

Usage:
    python scripts/processing/add_scotus_to_vector_db.py
"""

import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import lancedb
import openai
import pyarrow as pa
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent

try:
    sys.path.insert(0, str(PROJECT_ROOT))
    from app.config import get_settings

    settings = get_settings()
    VECTOR_DB_DIR = settings.vector_db_dir
    OPENAI_API_KEY = settings.openai_api_key
    EMBEDDING_MODEL = settings.embedding_model
except ImportError:
    VECTOR_DB_DIR = PROJECT_ROOT / "data" / "vector_db"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    EMBEDDING_MODEL = "text-embedding-3-large"

# SCOTUS database path
SCOTUS_DB_PATH = PROJECT_ROOT / "data" / "scotus" / "scotus_opinions.db"

# Maximum text length for embeddings
MAX_TEXT_LENGTH = 8000
BATCH_SIZE = 50


def get_embeddings(client: openai.OpenAI, texts: list[str]) -> list[list[float]]:
    """Get embeddings for a batch of texts from OpenAI"""
    response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
    return [e.embedding for e in response.data]


def load_opinions_from_db():
    """Load all opinions from the SQLite database."""
    if not SCOTUS_DB_PATH.exists():
        print(f"ERROR: SCOTUS database not found at {SCOTUS_DB_PATH}")
        print("Run 'python scripts/download/download_scotus_opinions.py' first")
        return []

    conn = sqlite3.connect(SCOTUS_DB_PATH)
    cursor = conn.cursor()

    # Join cases and opinions to get full information
    cursor.execute(
        """
        SELECT
            c.cluster_id,
            c.case_name,
            c.case_name_short,
            c.date_filed,
            c.citation,
            c.judges,
            o.opinion_id,
            o.type,
            o.author,
            o.plain_text
        FROM cases c
        JOIN opinions o ON c.id = o.case_id
        WHERE o.plain_text IS NOT NULL
          AND LENGTH(o.plain_text) > 100
        ORDER BY c.date_filed DESC
    """
    )

    opinions = cursor.fetchall()
    conn.close()

    return opinions


def prepare_documents(opinions):
    """Prepare opinion documents for embedding."""
    documents = []

    for row in opinions:
        (
            cluster_id,
            case_name,
            case_name_short,
            date_filed,
            citation,
            judges,
            opinion_id,
            opinion_type,
            author,
            plain_text,
        ) = row

        # Create a readable identifier
        display_name = case_name_short or case_name or f"Case {cluster_id}"
        year = date_filed[:4] if date_filed else "Unknown"

        # Opinion type labels
        type_labels = {
            "010combined": "Opinion of the Court",
            "015unamimous": "Unanimous Opinion",
            "020lead": "Lead Opinion",
            "025plurality": "Plurality Opinion",
            "030concurrence": "Concurring Opinion",
            "035concurrenceinpart": "Concurring in Part",
            "040dissent": "Dissenting Opinion",
            "045dissentinpart": "Dissenting in Part",
            "050addendum": "Addendum",
            "060rehearing": "Rehearing",
            "070onthemerits": "On the Merits",
            "080onremand": "On Remand",
        }
        type_label = type_labels.get(opinion_type, opinion_type or "Opinion")

        # Create identifier for the opinion - use full case name for better distinction
        # Prefer full case_name over case_name_short for clarity
        full_name = case_name or case_name_short or f"Case {cluster_id}"
        year = date_filed[:4] if date_filed else "Unknown"

        # Build identifier with citation if available
        if citation:
            identifier = f"{full_name}, {citation}"
        else:
            identifier = f"{full_name} ({year})"

        # Truncate text if needed
        text = (
            plain_text[:MAX_TEXT_LENGTH]
            if len(plain_text) > MAX_TEXT_LENGTH
            else plain_text
        )

        # Clean up text
        text = re.sub(r"\s+", " ", text).strip()

        # Create heading with metadata
        heading = f"{type_label}"
        if author:
            heading += f" by {author}"

        # Document text for embedding
        doc_text = f"{identifier}: {heading}\n\n{text}"

        documents.append(
            {
                "identifier": identifier,
                "heading": heading,
                "text": text,
                "title_number": "SCOTUS",  # Use "SCOTUS" as the "title" for filtering
                "source_type": "scotus",
                "cluster_id": cluster_id,
                "opinion_id": opinion_id,
                "case_name": case_name,
                "date_filed": date_filed,
                "citation": citation,
                "opinion_type": opinion_type,
                "doc_text": doc_text,
            }
        )

    return documents


def add_to_vector_db(documents):
    """Add SCOTUS opinions to the LanceDB vector database."""
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY not found!")
        return False

    # Initialize OpenAI client
    oai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

    # Connect to LanceDB
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(VECTOR_DB_DIR))

    # Check if SCOTUS table already exists
    existing_tables = db.table_names()
    if "scotus_opinions" in existing_tables:
        print("Dropping existing scotus_opinions table...")
        db.drop_table("scotus_opinions")

    # Generate embeddings in batches
    print(f"\nGenerating embeddings for {len(documents)} opinions...")
    all_embeddings = []

    for i in tqdm(range(0, len(documents), BATCH_SIZE), desc="Embedding"):
        batch = documents[i : i + BATCH_SIZE]
        texts = [d["doc_text"] for d in batch]

        try:
            embeddings = get_embeddings(oai_client, texts)
            all_embeddings.extend(embeddings)
        except Exception as e:
            print(f"\nError getting embeddings for batch {i}: {e}")
            # Add zero embeddings as placeholder
            dim = 3072 if "large" in EMBEDDING_MODEL else 1536
            all_embeddings.extend([[0.0] * dim] * len(batch))

        time.sleep(0.1)  # Rate limiting

    # Prepare data for LanceDB
    print("\nCreating vector table...")
    data = []
    for i, doc in enumerate(documents):
        data.append(
            {
                "identifier": doc["identifier"],
                "heading": doc["heading"],
                "text": doc["text"],
                "title_number": doc["title_number"],
                "source_type": doc["source_type"],
                "cluster_id": doc["cluster_id"],
                "opinion_id": doc["opinion_id"],
                "case_name": doc["case_name"],
                "date_filed": doc["date_filed"] or "",
                "citation": doc["citation"] or "",
                "opinion_type": doc["opinion_type"] or "",
                "vector": all_embeddings[i],
            }
        )

    # Create table
    table = db.create_table("scotus_opinions", data)

    # Create index for faster search
    print("Creating search index...")
    try:
        table.create_index(metric="cosine", num_partitions=16, num_sub_vectors=48)
    except Exception as e:
        print(f"  Note: Could not create index (may need more data): {e}")

    return True


def main():
    print("=" * 60)
    print("ADD SCOTUS OPINIONS TO VECTOR DATABASE")
    print("=" * 60)

    # Load opinions
    print("\nLoading opinions from database...")
    opinions = load_opinions_from_db()

    if not opinions:
        print("No opinions found to process.")
        return

    print(f"Found {len(opinions)} opinions")

    # Prepare documents
    print("\nPreparing documents...")
    documents = prepare_documents(opinions)
    print(f"Prepared {len(documents)} documents")

    # Add to vector database
    success = add_to_vector_db(documents)

    if success:
        print("\n" + "=" * 60)
        print("SUCCESS! SCOTUS opinions added to vector database")
        print(f"  Documents: {len(documents)}")
        print(f"  Database: {VECTOR_DB_DIR}")
        print("=" * 60)
    else:
        print("\nFailed to add opinions to vector database")


if __name__ == "__main__":
    main()
