"""
Add Documents to Vector Database (LanceDB)
A reusable script to add text documents from any folder to the vector database.

Usage:
    python add_documents.py <folder_path> [--doc-type <type>] [--prefix <prefix>]

Examples:
    python add_documents.py data/founding_documents --doc-type founding_document
    python add_documents.py data/case_law --doc-type case_law --prefix case
"""

import argparse
import logging
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import re
import time

import lancedb
import openai
from tqdm import tqdm

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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
    VECTOR_DB_DIR = settings.vector_db_dir
    OPENAI_API_KEY = settings.openai_api_key
    EMBEDDING_MODEL = settings.embedding_model
except ImportError:
    import os
    from dotenv import load_dotenv

    load_dotenv()
    DATA_DIR = PROJECT_ROOT / "data"
    VECTOR_DB_DIR = DATA_DIR / "vector_db"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    EMBEDDING_MODEL = "text-embedding-3-small"

BATCH_SIZE = 50  # Smaller batches for text documents


@dataclass
class DocumentChunk:
    """A chunk of text from a document"""

    id: str
    identifier: str
    heading: str
    text: str
    source_file: str
    document_type: str


def parse_text_file(
    filepath: Path, doc_type: str, id_prefix: str
) -> List[DocumentChunk]:
    """
    Parse a text file into chunks for embedding.

    Splits on section headers (lines in ALL CAPS or "ARTICLE/SECTION/AMENDMENT" patterns).
    Falls back to treating the whole file as one chunk if no sections found.
    """
    content = filepath.read_text(encoding="utf-8")
    filename = filepath.stem.replace("_", " ").title()

    chunks = []

    # Try to split by section headers
    # Match: ARTICLE I, AMENDMENT I, Section 1, or ALL CAPS lines
    section_pattern = r"\n((?:ARTICLE|AMENDMENT|SECTION|PREAMBLE)[^\n]*|[A-Z][A-Z\s\-]+(?:\([^)]+\))?)\n"

    parts = re.split(section_pattern, content)

    if len(parts) > 1:
        # We found sections
        current_heading = filename
        current_text = parts[0].strip()

        # If there's intro text before first heading, add it
        if current_text:
            chunk_id = f"{id_prefix}_{len(chunks)}"
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    identifier=f"{filename} - Introduction",
                    heading="Introduction",
                    text=current_text,
                    source_file=filepath.name,
                    document_type=doc_type,
                )
            )

        # Process heading/content pairs
        i = 1
        while i < len(parts):
            heading = parts[i].strip()
            text = parts[i + 1].strip() if i + 1 < len(parts) else ""

            if text and len(text) > 50:  # Only add if there's substantial content
                chunk_id = f"{id_prefix}_{len(chunks)}"
                chunks.append(
                    DocumentChunk(
                        id=chunk_id,
                        identifier=f"{filename} - {heading}",
                        heading=heading,
                        text=text,
                        source_file=filepath.name,
                        document_type=doc_type,
                    )
                )
            i += 2

    # If no sections found or very few, treat whole file as one chunk
    if len(chunks) < 2:
        chunks = [
            DocumentChunk(
                id=f"{id_prefix}_0",
                identifier=filename,
                heading=filename,
                text=content.strip(),
                source_file=filepath.name,
                document_type=doc_type,
            )
        ]

    return chunks


def get_embeddings(
    client: openai.OpenAI, texts: list[str], model: str
) -> list[list[float]]:
    """Get embeddings for a batch of texts from OpenAI"""
    response = client.embeddings.create(input=texts, model=model)
    return [e.embedding for e in response.data]


def add_documents_to_vectordb(
    folder_path: Path,
    doc_type: str = "document",
    id_prefix: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    """
    Add all text documents from a folder to the vector database.

    Args:
        folder_path: Path to folder containing .txt files
        doc_type: Document type for metadata (e.g., "founding_document", "case_law")
        id_prefix: Prefix for document IDs (defaults to doc_type)
        dry_run: If True, only show what would be added without actually adding

    Returns:
        True if successful, False otherwise
    """
    if id_prefix is None:
        id_prefix = doc_type.replace(" ", "_").replace("-", "_")

    logger.info("=" * 60)
    logger.info("ADDING DOCUMENTS TO VECTOR DATABASE (LanceDB)")
    logger.info(f"Folder: {folder_path}")
    logger.info(f"Document type: {doc_type}")
    logger.info(f"ID prefix: {id_prefix}")
    logger.info(f"Embedding model: {EMBEDDING_MODEL}")
    logger.info("=" * 60)

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not found")
        return False

    if not folder_path.exists():
        logger.error(f"Folder not found: {folder_path}")
        return False

    # Find all text files
    txt_files = list(folder_path.glob("*.txt"))
    if not txt_files:
        logger.error(f"No .txt files found in {folder_path}")
        return False

    logger.info(f"Found {len(txt_files)} text files")

    # Parse all files into chunks
    all_chunks: List[DocumentChunk] = []
    for filepath in txt_files:
        file_prefix = f"{id_prefix}_{filepath.stem}"
        chunks = parse_text_file(filepath, doc_type, file_prefix)
        logger.info(f"  {filepath.name}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    logger.info(f"Total chunks to add: {len(all_chunks)}")

    if dry_run:
        logger.info("\n[DRY RUN] Would add the following chunks:")
        for chunk in all_chunks[:10]:  # Show first 10
            logger.info(f"  {chunk.id}: {chunk.identifier}")
        if len(all_chunks) > 10:
            logger.info(f"  ... and {len(all_chunks) - 10} more")
        return True

    # Connect to database
    if not VECTOR_DB_DIR or not VECTOR_DB_DIR.exists():
        logger.error(f"Vector DB not found at {VECTOR_DB_DIR}")
        logger.info("Run create_vector_db.py first")
        return False

    # Open LanceDB
    db = lancedb.connect(str(VECTOR_DB_DIR))

    try:
        table = db.open_table("uscode")
        current_count = table.count_rows()
        logger.info(f"Found existing table with {current_count} documents")
    except Exception as e:
        logger.error(f"Could not open table 'uscode': {e}")
        logger.info("Run create_vector_db.py first to create the table")
        return False

    # Initialize OpenAI client
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

    # Prepare documents for embedding
    texts_to_embed = []
    for chunk in all_chunks:
        doc_text = f"{chunk.identifier}: {chunk.heading}\n\n{chunk.text}"
        # Truncate if too long
        if len(doc_text) > 8000:
            doc_text = doc_text[:8000]
        texts_to_embed.append(doc_text)

    # Get embeddings in batches
    logger.info(f"Getting embeddings for {len(texts_to_embed)} chunks...")
    all_embeddings = []

    for i in tqdm(range(0, len(texts_to_embed), BATCH_SIZE), desc="Embedding"):
        batch_texts = texts_to_embed[i : i + BATCH_SIZE]

        try:
            embeddings = get_embeddings(openai_client, batch_texts, EMBEDDING_MODEL)
            all_embeddings.extend(embeddings)
        except Exception as e:
            logger.error(f"Error getting embeddings: {e}")
            return False

        # Rate limiting
        time.sleep(0.1)

    # Prepare records for LanceDB.
    # NOTE: Must match the existing table schema. The default US Code table has:
    #   identifier, heading, title, text, text_length, vector
    records = []
    default_title = (
        "Founding Documents"
        if doc_type.strip().lower() in {"founding_document", "founding documents"}
        else doc_type.strip().title()
    )
    for chunk, embedding in zip(all_chunks, all_embeddings):
        records.append(
            {
                "identifier": chunk.identifier,
                "heading": chunk.heading,
                "title": default_title,
                # Store the raw chunk text for display; embeddings were computed from
                # identifier/heading + text for better retrieval.
                "text": chunk.text,
                "text_length": len(chunk.text),
                "vector": embedding,
            }
        )

    # Add to table
    logger.info(f"Adding {len(records)} records to database...")
    try:
        table.add(records)
    except Exception as e:
        logger.error(f"Error adding records: {e}")
        return False

    new_count = table.count_rows()
    logger.info("=" * 60)
    logger.info("DOCUMENTS ADDED SUCCESSFULLY")
    logger.info("=" * 60)
    logger.info(f"Previous count: {current_count}")
    logger.info(f"New count: {new_count}")
    logger.info(f"Added: {len(all_chunks)} chunks from {len(txt_files)} files")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Add text documents to the vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python add_documents.py data/founding_documents --doc-type founding_document
  python add_documents.py data/case_law --doc-type case_law --prefix case
  python add_documents.py data/regulations --doc-type regulation --dry-run
        """,
    )
    parser.add_argument(
        "folder", type=str, help="Path to folder containing .txt files to add"
    )
    parser.add_argument(
        "--doc-type",
        type=str,
        default="document",
        help="Document type for metadata (default: 'document')",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="ID prefix for documents (default: based on doc-type)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be added without actually adding",
    )

    args = parser.parse_args()

    # Resolve folder path
    folder_path = Path(args.folder)
    if not folder_path.is_absolute():
        folder_path = PROJECT_ROOT / folder_path

    success = add_documents_to_vectordb(
        folder_path=folder_path,
        doc_type=args.doc_type,
        id_prefix=args.prefix,
        dry_run=args.dry_run,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
