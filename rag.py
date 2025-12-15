"""
RAG (Retrieval-Augmented Generation) for US Code
Answer questions using retrieved code sections + LLM
"""

import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Directories
DATA_DIR = Path(__file__).parent / "data"
VECTOR_DB_DIR = DATA_DIR / "vector_db"


def get_relevant_sections(query: str, n_results: int = 5):
    """Retrieve relevant sections from vector database"""

    if not VECTOR_DB_DIR.exists():
        raise Exception("Vector database not found. Run: python create_vector_db.py")

    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY not found in environment")

    # Create OpenAI embedding function
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key, model_name="text-embedding-3-large"
    )

    # Load collection
    client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
    collection = client.get_collection(name="uscode", embedding_function=openai_ef)

    # Search
    results = collection.query(query_texts=[query], n_results=n_results)

    if not results["documents"][0]:
        return []

    # Format results
    sections = []
    for doc, meta, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        sections.append(
            {
                "identifier": meta["identifier"],
                "heading": meta["heading"],
                "text": doc,
                "relevance": 1 - distance,
            }
        )

    return sections


def answer_with_openai(question: str, sections: list, model: str = "gpt-4o"):
    """Generate answer using OpenAI"""
    try:
        from openai import OpenAI
    except ImportError:
        raise Exception("OpenAI library not installed. Run: pip install openai")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY not found in environment")

    client = OpenAI(api_key=api_key)

    # Build context from sections
    context = "\n\n".join(
        [f"[{s['identifier']}] {s['heading']}\n{s['text'][:2000]}" for s in sections]
    )

    # Create prompt
    prompt = f"""You are a legal expert assistant helping users understand US federal law. Answer the question based ONLY on the provided US Code sections. Be precise and cite specific sections when relevant.

US CODE SECTIONS:
{context}

QUESTION: {question}

ANSWER (cite specific sections):"""

    # Call OpenAI
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful legal expert who answers questions based on US federal law. Always cite specific sections and be precise.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content


def answer_with_anthropic(
    question: str, sections: list, model: str = "claude-sonnet-4-20250514"
):
    """Generate answer using Anthropic Claude"""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise Exception("Anthropic library not installed. Run: pip install anthropic")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY not found in environment")

    client = Anthropic(api_key=api_key)

    # Build context from sections
    context = "\n\n".join(
        [f"[{s['identifier']}] {s['heading']}\n{s['text'][:2000]}" for s in sections]
    )

    # Create prompt
    prompt = f"""You are a legal expert assistant helping users understand US federal law. Answer the question based ONLY on the provided US Code sections. Be precise and cite specific sections when relevant.

US CODE SECTIONS:
{context}

QUESTION: {question}

ANSWER (cite specific sections):"""

    # Call Anthropic
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0.3,
        system="You are a helpful legal expert who answers questions based on US federal law. Always cite specific sections and be precise.",
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def rag_query(
    question: str,
    provider: str = "openai",
    model: str = None,
    n_sections: int = 5,
    verbose: bool = True,
):
    """
    Complete RAG pipeline: retrieve + generate answer

    Args:
        question: User's question
        provider: 'openai' or 'anthropic'
        model: Model name (optional, uses defaults)
        n_sections: Number of sections to retrieve
        verbose: Print retrieval info

    Returns:
        dict with answer, sections, and metadata
    """

    if verbose:
        print(f"\n{'='*70}")
        print(f"QUESTION: {question}")
        print(f"{'='*70}\n")
        print(f"📚 Retrieving relevant sections...")

    # Retrieve relevant sections
    sections = get_relevant_sections(question, n_sections)

    if not sections:
        return {
            "answer": "No relevant sections found in the US Code.",
            "sections": [],
            "provider": provider,
        }

    if verbose:
        print(f"✓ Found {len(sections)} relevant sections\n")
        print("Most relevant:")
        for i, s in enumerate(sections[:3], 1):
            print(
                f"  {i}. {s['identifier']}: {s['heading']} ({s['relevance']:.1%} match)"
            )
        print(f"\n🤖 Generating answer using {provider.upper()}...")

    # Generate answer
    if provider.lower() == "openai":
        default_model = model or "gpt-4o"
        answer = answer_with_openai(question, sections, default_model)
    elif provider.lower() == "anthropic":
        default_model = model or "claude-3-5-sonnet-20241022"
        answer = answer_with_anthropic(question, sections, default_model)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'openai' or 'anthropic'")

    if verbose:
        print(f"\n{'='*70}")
        print("ANSWER:")
        print(f"{'='*70}\n")
        print(answer)
        print(f"\n{'='*70}")
        print(f"Sources: {len(sections)} sections")
        print(f"{'='*70}\n")

    return {
        "answer": answer,
        "sections": sections,
        "provider": provider,
        "model": default_model,
    }


if __name__ == "__main__":
    import sys

    # Example questions
    examples = [
        "How long does copyright protection last?",
        "What are the criminal penalties for wire fraud?",
        "Can I deduct home office expenses on my taxes?",
        "What is the minimum wage under federal law?",
        "What constitutes workplace discrimination?",
    ]

    if len(sys.argv) > 1:
        # Question from command line
        question = " ".join(sys.argv[1:])

        # Check for provider flag
        provider = "openai"
        if "--claude" in sys.argv or "--anthropic" in sys.argv:
            provider = "anthropic"
            question = (
                question.replace("--claude", "").replace("--anthropic", "").strip()
            )

        result = rag_query(question, provider=provider)
    else:
        # Interactive mode
        print(
            """
╔══════════════════════════════════════════════════════════════════╗
║              RAG - Ask Questions About US Code                   ║
╚══════════════════════════════════════════════════════════════════╝

Ask natural language questions and get answers based on actual US Code.

Examples:
"""
        )
        for ex in examples:
            print(f"  • {ex}")

        print("\nOptions:")
        print("  --claude    Use Claude instead of GPT-4")
        print("  quit        Exit")
        print()

        while True:
            try:
                question = input("\n💬 Your question: ").strip()

                if question.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    break

                if not question:
                    continue

                # Check for provider
                provider = "openai"
                if question.startswith("--claude"):
                    provider = "anthropic"
                    question = question.replace("--claude", "").strip()

                result = rag_query(question, provider=provider)

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
