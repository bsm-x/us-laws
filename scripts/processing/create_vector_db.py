"""
Create Vector Database for US Code
Uses OpenAI text-embedding-3-small model for embeddings
Parses XML files from the uscode folder and creates searchable LanceDB database
"""

import os
import re
import time
from pathlib import Path
from xml.etree import ElementTree as ET
from dataclasses import dataclass

import lancedb
import openai
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables from .env file
load_dotenv()

# Configuration - try to use app config, fall back to env vars
PROJECT_ROOT = Path(__file__).parent.parent.parent

try:
    import sys

    sys.path.insert(0, str(PROJECT_ROOT))
    from app.config import get_settings

    settings = get_settings()
    DATA_DIR = settings.data_dir
    USCODE_DIR = settings.uscode_dir
    VECTOR_DB_DIR = settings.vector_db_dir
    OPENAI_API_KEY = settings.openai_api_key
    EMBEDDING_MODEL = settings.embedding_model
    BATCH_SIZE = settings.vector_batch_size
except ImportError:
    DATA_DIR = PROJECT_ROOT / "data"
    USCODE_DIR = DATA_DIR / "uscode"
    VECTOR_DB_DIR = DATA_DIR / "vector_db"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    # Embedding model options:
    #   - "text-embedding-3-small": Good quality, 1536 dims, $0.02/1M tokens
    #   - "text-embedding-3-large": Best quality, 3072 dims, $0.13/1M tokens
    EMBEDDING_MODEL = "text-embedding-3-large"
    BATCH_SIZE = 100

MAX_TEXT_LENGTH = 8000  # Max characters per document


@dataclass
class Section:
    """Represents a US Code section"""

    identifier: str
    heading: str
    text: str
    title_number: str


def extract_text_from_element(element: ET.Element) -> str:
    """Recursively extract all text from an XML element"""
    texts = []

    if element.text:
        texts.append(element.text.strip())

    for child in element:
        child_text = extract_text_from_element(child)
        if child_text:
            texts.append(child_text)
        if child.tail:
            texts.append(child.tail.strip())

    return " ".join(filter(None, texts))


def parse_xml_file(xml_path: Path) -> list[Section]:
    """Parse a US Code XML file and extract all sections"""
    sections = []

    folder_name = xml_path.parent.name
    title_match = re.search(r"title_(\d+)", folder_name)
    title_number = title_match.group(1) if title_match else "unknown"

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        ns_uri = "{http://xml.house.gov/schemas/uslm/1.0}"

        for section in root.iter(f"{ns_uri}section"):
            identifier = section.get("identifier", "")

            heading_elem = section.find(f"{ns_uri}heading")
            heading = (
                extract_text_from_element(heading_elem)
                if heading_elem is not None
                else ""
            )

            num_elem = section.find(f"{ns_uri}num")
            section_num = (
                extract_text_from_element(num_elem) if num_elem is not None else ""
            )

            content_parts = []

            content_elem = section.find(f"{ns_uri}content")
            if content_elem is not None:
                content_parts.append(extract_text_from_element(content_elem))

            for subsection in section.findall(f"{ns_uri}subsection"):
                subsection_text = extract_text_from_element(subsection)
                if subsection_text:
                    content_parts.append(subsection_text)

            text = " ".join(filter(None, content_parts))

            if text and len(text) > 10:
                sections.append(
                    Section(
                        identifier=identifier or f"Title {title_number} {section_num}",
                        heading=heading or "Untitled Section",
                        text=text,
                        title_number=title_number,
                    )
                )

    except ET.ParseError as e:
        print(f"  Warning: Failed to parse {xml_path.name}: {e}")
    except Exception as e:
        print(f"  Warning: Error processing {xml_path.name}: {e}")

    return sections


def get_embeddings(
    client: openai.OpenAI, texts: list[str], model: str
) -> list[list[float]]:
    """Get embeddings for a batch of texts from OpenAI"""
    response = client.embeddings.create(input=texts, model=model)
    return [e.embedding for e in response.data]


def create_vector_database():
    """Create LanceDB vector database from all US Code XML files"""

    print("=" * 60)
    print("US CODE VECTOR DATABASE CREATOR")
    print("=" * 60)
    print(f"Embedding Model: {EMBEDDING_MODEL}")
    print(f"Data Directory: {USCODE_DIR}")
    print(f"Output Directory: {VECTOR_DB_DIR}")
    print("=" * 60)

    if not OPENAI_API_KEY:
        print("\nERROR: OPENAI_API_KEY not found in .env file!")
        return False

    # Initialize OpenAI client
    oai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

    # Find all XML files
    print("\nScanning for XML files...")
    xml_files = sorted(USCODE_DIR.rglob("*.xml"))

    if not xml_files:
        print("ERROR: No XML files found in", USCODE_DIR)
        return False

    print(f"Found {len(xml_files)} XML files")

    # Parse all XML files
    print("\nParsing XML files...")
    all_sections = []

    for xml_file in tqdm(xml_files, desc="Parsing"):
        sections = parse_xml_file(xml_file)
        all_sections.extend(sections)

    print(f"\nExtracted {len(all_sections)} sections from XML files")

    if not all_sections:
        print("ERROR: No sections extracted from XML files!")
        return False

    # Prepare documents
    print("\nPreparing documents...")
    documents = []

    for section in all_sections:
        doc_text = f"{section.identifier}: {section.heading}\n\n{section.text}"
        if len(doc_text) > MAX_TEXT_LENGTH:
            doc_text = doc_text[:MAX_TEXT_LENGTH] + "..."

        documents.append(
            {
                "identifier": section.identifier,
                "heading": section.heading,
                "title": section.title_number,
                "text": doc_text,
                "text_length": len(section.text),
            }
        )

    # Get embeddings in batches
    print(f"\nGetting embeddings for {len(documents)} documents...")
    print(f"Batch size: {BATCH_SIZE}")
    print("This will use OpenAI API credits.\n")

    all_embeddings = []

    for i in tqdm(range(0, len(documents), BATCH_SIZE), desc="Embedding"):
        batch = documents[i : i + BATCH_SIZE]
        batch_texts = [d["text"] for d in batch]

        max_retries = 5
        for attempt in range(max_retries):
            try:
                embeddings = get_embeddings(oai_client, batch_texts, EMBEDDING_MODEL)
                all_embeddings.extend(embeddings)
                time.sleep(0.2)  # Rate limit delay
                break
            except Exception as e:
                if "rate" in str(e).lower() or "429" in str(e):
                    wait_time = 2 ** (attempt + 1)
                    print(f"\n  Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"\n  Error: {e}")
                    if attempt == max_retries - 1:
                        raise

    print(f"\nGot {len(all_embeddings)} embeddings")

    # Add embeddings to documents
    for doc, emb in zip(documents, all_embeddings):
        doc["vector"] = emb

    # Create LanceDB database
    print("\nCreating LanceDB database...")
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)

    db = lancedb.connect(str(VECTOR_DB_DIR))
    table = db.create_table("uscode", documents, mode="overwrite")

    print(f"Created table 'uscode' with {table.count_rows()} rows")

    # Test the database
    print("\n" + "-" * 60)
    print("Testing database with sample query...")

    try:
        # Get embedding for test query
        test_query = "What is the definition of marriage?"
        query_emb = get_embeddings(oai_client, [test_query], EMBEDDING_MODEL)[0]

        results = table.search(query_emb).limit(3).to_list()

        print(f"\nQuery: '{test_query}'")
        print("Top 3 results:\n")

        for i, result in enumerate(results, 1):
            print(f"{i}. {result['identifier']}")
            print(f"   {result['heading']}")
            print(f"   Preview: {result['text'][:150]}...")
            print()

    except Exception as e:
        print(f"Test query failed: {e}")

    print("=" * 60)
    print("COMPLETE!")
    print(f"Database saved to: {VECTOR_DB_DIR}")
    print("=" * 60)

    return True


if __name__ == "__main__":
    print("\nUS Code Vector Database Creator")
    print("-" * 40)

    response = (
        input(
            "\nThis will create a new vector database using OpenAI embeddings.\nProceed? (yes/no): "
        )
        .strip()
        .lower()
    )

    if response in ("yes", "y"):
        success = create_vector_database()
        if success:
            print("\nVector database created successfully!")
        else:
            print("\nFailed to create vector database.")
            exit(1)
    else:
        print("Cancelled.")
