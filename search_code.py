"""
Semantic Search for US Code
Search across all sections using natural language
"""

import chromadb
from pathlib import Path
import sys

# Directories
DATA_DIR = Path(__file__).parent / "data"
VECTOR_DB_DIR = DATA_DIR / "vector_db"


def search(query: str, n_results: int = 10):
    """Search the US Code vector database"""

    if not VECTOR_DB_DIR.exists():
        print("❌ Vector database not found!")
        print("Run: python create_vector_db.py")
        return

    try:
        client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
        collection = client.get_collection("uscode")
    except Exception as e:
        print(f"❌ Error loading database: {e}")
        print("Run: python create_vector_db.py")
        return

    print("=" * 70)
    print(f"SEARCHING: {query}")
    print("=" * 70)

    # Search
    results = collection.query(query_texts=[query], n_results=n_results)

    if not results["documents"][0]:
        print("\nNo results found.")
        return

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

    print(f"\n{'=' * 70}")
    print(f"Search complete. Showing top {len(results['documents'][0])} results.")


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
