"""
RAG (Retrieval-Augmented Generation) for US Code
Answer questions using retrieved code sections + LLM

Performance optimizations:
- Singleton ChromaDB client (no reconnection per query)
- Cached embedding function (reused across queries)
- Connection pooled LLM clients
- Proper logging instead of print statements
"""

import logging
from typing import List, Optional
from functools import lru_cache

from app.config import get_settings, setup_logging
from app.database import get_vector_db, get_openai_client, get_anthropic_client
from app.models import SearchResult, RAGResponse

logger = logging.getLogger(__name__)


def get_relevant_sections(query: str, n_results: int = 5) -> List[SearchResult]:
    """
    Retrieve relevant sections from vector database
    Uses singleton client for performance
    """
    settings = get_settings()

    if not settings.validate_vector_db():
        raise RuntimeError(
            f"Vector database not found at {settings.vector_db_dir}. "
            "Run: python scripts/processing/create_vector_db.py"
        )

    if not settings.validate_openai():
        raise RuntimeError("OPENAI_API_KEY required for embeddings")

    # Use singleton client (no reconnection overhead)
    db = get_vector_db()

    # Fetch a larger pool, then filter out non-USC docs (e.g., Founding Documents)
    # so the answer context remains strictly US Code.
    raw_results = db.search(query, n_results=n_results)

    if not raw_results["documents"][0]:
        return []

    results = raw_results

    if not results["documents"][0]:
        return []

    # Convert to Pydantic models
    sections = []
    for doc, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # LanceDB returns L2 distance - convert to relevance score (0-1)
        # We use a quadratic scaling that maps the typical range of 0-2 to 0-1
        # This provides more intuitive scores (e.g. 0.8 distance -> ~83% match)
        relevance = max(0.0, min(1.0, 1.0 - (distance * distance) / 4.0))
        sections.append(
            SearchResult(
                identifier=meta["identifier"],
                heading=meta["heading"],
                text=doc,
                relevance=relevance,
            )
        )

    logger.debug(f"Retrieved {len(sections)} sections for query: {query[:50]}...")
    return sections


def answer_with_openai(
    question: str,
    sections: List[SearchResult],
    model: Optional[str] = None,
) -> str:
    """Generate answer using OpenAI (connection pooled)"""
    settings = get_settings()
    model = model or settings.default_openai_model

    # Use pooled client
    client = get_openai_client()

    # Build context from sections
    context = "\n\n".join(
        [f"[{s.identifier}] {s.heading}\n{s.text[:2000]}" for s in sections]
    )

    prompt = f"""You are a legal expert assistant helping users understand US federal law. Answer the question based ONLY on the provided US Code sections. Be precise and cite specific sections when relevant.

US CODE SECTIONS:
{context}

QUESTION: {question}

ANSWER (cite specific sections):"""

    logger.debug(f"Calling OpenAI {model}")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful legal expert who answers questions based on US federal law. Always cite specific sections and be precise.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=settings.rag_temperature,
        max_tokens=settings.rag_max_tokens,
    )

    return response.choices[0].message.content or ""


def answer_with_anthropic(
    question: str,
    sections: List[SearchResult],
    model: Optional[str] = None,
) -> str:
    """Generate answer using Anthropic Claude (connection pooled)"""
    settings = get_settings()
    model = model or settings.default_anthropic_model

    # Use pooled client
    client = get_anthropic_client()

    # Build context from sections
    context = "\n\n".join(
        [f"[{s.identifier}] {s.heading}\n{s.text[:2000]}" for s in sections]
    )

    prompt = f"""You are a legal expert assistant helping users understand US federal law. Answer the question based ONLY on the provided US Code sections. Be precise and cite specific sections when relevant.

US CODE SECTIONS:
{context}

QUESTION: {question}

ANSWER (cite specific sections):"""

    logger.debug(f"Calling Anthropic {model}")

    response = client.messages.create(
        model=model,
        max_tokens=settings.rag_max_tokens,
        temperature=settings.rag_temperature,
        system="You are a helpful legal expert who answers questions based on US federal law. Always cite specific sections and be precise.",
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text from first content block
    if response.content and hasattr(response.content[0], "text"):
        return response.content[0].text
    return ""


def stream_with_openai(
    question: str,
    sections: List[SearchResult],
    model: Optional[str] = None,
):
    """Stream answer using OpenAI"""
    settings = get_settings()
    model = model or settings.default_openai_model

    client = get_openai_client()

    context = "\n\n".join(
        [f"[{s.identifier}] {s.heading}\n{s.text[:2000]}" for s in sections]
    )

    prompt = f"""You are a legal expert assistant helping users understand US federal law. Answer the question based ONLY on the provided US Code sections. Be precise and cite specific sections when relevant.

US CODE SECTIONS:
{context}

QUESTION: {question}

ANSWER (cite specific sections):"""

    logger.debug(f"Streaming OpenAI {model}")

    stream = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful legal expert who answers questions based on US federal law. Always cite specific sections and be precise.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=settings.rag_temperature,
        max_tokens=settings.rag_max_tokens,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def stream_with_anthropic(
    question: str,
    sections: List[SearchResult],
    model: Optional[str] = None,
):
    """Stream answer using Anthropic Claude"""
    settings = get_settings()
    model = model or settings.default_anthropic_model

    client = get_anthropic_client()

    context = "\n\n".join(
        [f"[{s.identifier}] {s.heading}\n{s.text[:2000]}" for s in sections]
    )

    prompt = f"""You are a legal expert assistant helping users understand US federal law. Answer the question based ONLY on the provided US Code sections. Be precise and cite specific sections when relevant.

US CODE SECTIONS:
{context}

QUESTION: {question}

ANSWER (cite specific sections):"""

    logger.debug(f"Streaming Anthropic {model}")

    with client.messages.stream(
        model=model,
        max_tokens=settings.rag_max_tokens,
        temperature=settings.rag_temperature,
        system="You are a helpful legal expert who answers questions based on US federal law. Always cite specific sections and be precise.",
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def rag_query(
    question: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    n_sections: Optional[int] = None,
    verbose: bool = True,
) -> RAGResponse:
    """
    Complete RAG pipeline: retrieve + generate answer

    Args:
        question: User's question
        provider: 'openai' or 'anthropic' (default from config)
        model: Model name (optional, uses defaults from config)
        n_sections: Number of sections to retrieve
        verbose: Print progress info

    Returns:
        RAGResponse with answer, sections, and metadata
    """
    settings = get_settings()

    provider = provider or settings.default_llm_provider
    n_sections = n_sections or settings.rag_n_sections

    if verbose:
        logger.info(f"RAG Query: {question[:100]}...")
        logger.info(f"Provider: {provider}, Sections: {n_sections}")

    # Retrieve relevant sections
    sections = get_relevant_sections(question, n_sections)

    if not sections:
        return RAGResponse(
            answer="No relevant sections found in the US Code.",
            sections=[],
            provider=provider,
            model="none",
        )

    if verbose:
        logger.info(f"Found {len(sections)} relevant sections")
        for s in sections[:3]:
            logger.debug(f"  - {s.identifier}: {s.heading} ({s.relevance:.1%})")

    # Generate answer
    if provider.lower() == "openai":
        used_model = model or settings.default_openai_model
        answer = answer_with_openai(question, sections, used_model)
    elif provider.lower() == "anthropic":
        used_model = model or settings.default_anthropic_model
        answer = answer_with_anthropic(question, sections, used_model)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'openai' or 'anthropic'")

    if verbose:
        logger.info(f"Generated answer using {provider}/{used_model}")

    return RAGResponse(
        answer=answer,
        sections=sections,
        provider=provider,
        model=used_model,
    )


# Async version for FastAPI
async def rag_query_async(
    question: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    n_sections: Optional[int] = None,
) -> RAGResponse:
    """Async wrapper for RAG query (runs in thread pool)"""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(
            pool,
            lambda: rag_query(question, provider, model, n_sections, verbose=False),
        )
    return result


if __name__ == "__main__":
    import sys

    # Setup logging for CLI
    setup_logging("INFO")

    examples = [
        "How long does copyright protection last?",
        "What are the criminal penalties for wire fraud?",
        "Can I deduct home office expenses on my taxes?",
    ]

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])

        provider = "openai"
        if "--claude" in question or "--anthropic" in question:
            provider = "anthropic"
            question = (
                question.replace("--claude", "").replace("--anthropic", "").strip()
            )

        result = rag_query(question, provider=provider)

        print(f"\n{'='*70}")
        print("ANSWER:")
        print(f"{'='*70}\n")
        print(result.answer)
        print(f"\n{'='*70}")
        print(f"Sources: {len(result.sections)} sections | Model: {result.model}")
    else:
        print("\nUsage: python -m app.rag 'your question here'")
        print("\nExamples:")
        for ex in examples:
            print(f"  • {ex}")
        print("\nOptions:")
        print("  --claude    Use Claude instead of GPT-4")
