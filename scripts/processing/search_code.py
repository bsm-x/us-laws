"""
Semantic Search for US Code
Search across all sections using natural language

Uses singleton DB client for performance when called multiple times
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional

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

# Try to use app modules, fall back to direct chromadb
try:
    from app.database import get_vector_db
    from app.config import get_settings

    USE_APP_DB = True
    settings = get_settings()
    VECTOR_DB_DIR = settings.vector_db_dir
except ImportError:
    USE_APP_DB = False
    import chromadb

    VECTOR_DB_DIR = PROJECT_ROOT / "data" / "vector_db"


def search(query: str, n_results: int = 10) -> Optional[List[dict]]:
    """Search the US Code vector database"""

    if not VECTOR_DB_DIR.exists():
        logger.error("Vector database not found!")
        logger.info("Run: python scripts/processing/create_vector_db.py")
        return None

    try:
        if USE_APP_DB:
            # Use singleton client (fast)
            db = get_vector_db()
            results = db.search(query, n_results=n_results)
        else:
            # Direct chromadb access
            client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
            collection = client.get_collection("uscode")
            results = collection.query(query_texts=[query], n_results=n_results)
    except Exception as e:
        logger.error(f"Error searching database: {e}")
        return None

    print("=" * 70)
    print(f"SEARCHING: {query}")
    print("=" * 70)

    if not results["documents"][0]:
        print("\nNo results found.")
        return []

    # Build results list
    search_results = []

    # Display results
    print(f"\nFound {len(results['documents'][0])} relevant sections:\n")

    for i, (doc, meta, distance) in enumerate(
        zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
    ):
        print(f"\n{'─' * 70}")
        print(f"#{i+1} | {meta['identifier']}")
        print(f"{'─' * 70}")
        print(f"Heading: {meta['heading']}")
        print(f"Relevance: {1 - distance:.2%}")
        print(f"\nText Preview:")

        # Extract just the text part (after heading)
        text_start = doc.find("\n\n")
        if text_start > 0:
            text = doc[text_start + 2 :]
        else:
            text = doc

        # Show first 500 chars
        preview = text[:500].strip()
        if len(text) > 500:
            preview += "..."

        print(preview)

        search_results.append(
            {
                "identifier": meta["identifier"],
                "heading": meta["heading"],
                "relevance": 1 - distance,
                "preview": preview,
            }
        )

    print(f"\n{'=' * 70}")
    print(f"Search complete. Showing top {len(results['documents'][0])} results.")

    return search_results


def interactive_search():
    """Interactive search mode"""
    print(
        """
╔══════════════════════════════════════════════════════════════════╗
║            US CODE SEMANTIC SEARCH                               ║
╚══════════════════════════════════════════════════════════════════╝

Search the entire US Code using natural language queries.
Examples:
  • "copyright protection duration"
  • "criminal penalties for insider trading"
  • "tax deductions for home offices"
  • "rules about workplace discrimination"

Type 'quit' or 'exit' to stop.
    """
    )

    while True:
        try:
            query = input("\n🔍 Search: ").strip()

            if query.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if not query:
                continue

            # Check for number of results flag
            n_results = 10
            if query.startswith("-n"):
                parts = query.split(" ", 2)
                if len(parts) >= 3:
                    try:
                        n_results = int(parts[1])
                        query = parts[2]
                    except:
                        pass

            search(query, n_results)

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Command line search
        query = " ".join(sys.argv[1:])

        # Check for -n flag
        n_results = 10
        if sys.argv[1] == "-n" and len(sys.argv) > 3:
            try:
                n_results = int(sys.argv[2])
                query = " ".join(sys.argv[3:])
            except:
                pass

        search(query, n_results)
    else:
        # Interactive mode
        interactive_search()
