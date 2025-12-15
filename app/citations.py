"""
Citation Graph API module for the US Laws application.
Provides functions to query the citation database.
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.config import get_settings

settings = get_settings()
CITATION_DB = settings.data_dir / "citations.db"


@dataclass
class RelatedSection:
    """A section related by citation"""

    identifier: str
    title: str
    section: str
    relationship: str  # "cites" or "cited_by"
    citation_text: Optional[str] = None


def get_db_connection():
    """Get a connection to the citation database"""
    if not CITATION_DB.exists():
        return None
    return sqlite3.connect(CITATION_DB)


def citation_db_exists() -> bool:
    """Check if the citation database exists"""
    return CITATION_DB.exists()


def get_sections_that_cite(identifier: str, limit: int = 20) -> List[RelatedSection]:
    """Get sections that cite the given section"""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT source_identifier, source_title, source_section, citation_text
        FROM citations
        WHERE target_identifier = ?
        LIMIT ?
    """,
        (identifier, limit),
    )

    results = []
    for row in cursor.fetchall():
        results.append(
            RelatedSection(
                identifier=row[0],
                title=row[1],
                section=row[2],
                relationship="cited_by",
                citation_text=row[3],
            )
        )

    conn.close()
    return results


def get_sections_cited_by(identifier: str, limit: int = 20) -> List[RelatedSection]:
    """Get sections that the given section cites"""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT target_identifier, target_title, target_section, citation_text
        FROM citations
        WHERE source_identifier = ?
        LIMIT ?
    """,
        (identifier, limit),
    )

    results = []
    for row in cursor.fetchall():
        results.append(
            RelatedSection(
                identifier=row[0],
                title=row[1],
                section=row[2],
                relationship="cites",
                citation_text=row[3],
            )
        )

    conn.close()
    return results


def get_related_sections(
    identifier: str, limit: int = 10
) -> Dict[str, List[Dict[str, Any]]]:
    """Get all related sections (both directions) for a given section"""
    cited_by = get_sections_that_cite(identifier, limit)
    cites = get_sections_cited_by(identifier, limit)

    return {
        "cited_by": [
            {
                "identifier": s.identifier,
                "title": s.title,
                "section": s.section,
                "citation_text": s.citation_text,
            }
            for s in cited_by
        ],
        "cites": [
            {
                "identifier": s.identifier,
                "title": s.title,
                "section": s.section,
                "citation_text": s.citation_text,
            }
            for s in cites
        ],
        "total_cited_by": len(cited_by),
        "total_cites": len(cites),
    }


def get_citation_stats() -> Dict[str, Any]:
    """Get statistics about the citation graph"""
    conn = get_db_connection()
    if not conn:
        return {"error": "Citation database not found"}

    cursor = conn.cursor()

    # Total citations
    cursor.execute("SELECT COUNT(*) FROM citations")
    total = cursor.fetchone()[0]

    # Unique citing sections
    cursor.execute("SELECT COUNT(DISTINCT source_identifier) FROM citations")
    citing_sections = cursor.fetchone()[0]

    # Unique cited sections
    cursor.execute("SELECT COUNT(DISTINCT target_identifier) FROM citations")
    cited_sections = cursor.fetchone()[0]

    # Most cited sections
    cursor.execute(
        """
        SELECT target_identifier, target_title, target_section, COUNT(*) as cnt
        FROM citations
        GROUP BY target_identifier
        ORDER BY cnt DESC
        LIMIT 10
    """
    )
    most_cited = [
        {"identifier": row[0], "title": row[1], "section": row[2], "count": row[3]}
        for row in cursor.fetchall()
    ]

    # Most citing sections
    cursor.execute(
        """
        SELECT source_identifier, source_title, source_section, COUNT(*) as cnt
        FROM citations
        GROUP BY source_identifier
        ORDER BY cnt DESC
        LIMIT 10
    """
    )
    most_citing = [
        {"identifier": row[0], "title": row[1], "section": row[2], "count": row[3]}
        for row in cursor.fetchall()
    ]

    conn.close()

    return {
        "total_citations": total,
        "citing_sections": citing_sections,
        "cited_sections": cited_sections,
        "most_cited": most_cited,
        "most_citing": most_citing,
    }


def search_citation_path(
    source_identifier: str, target_identifier: str, max_depth: int = 3
) -> List[List[str]]:
    """
    Find citation paths between two sections (BFS).
    Returns list of paths, where each path is a list of identifiers.
    """
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()

    # BFS to find paths
    visited = {source_identifier}
    queue = [[source_identifier]]
    found_paths = []

    while queue and len(found_paths) < 5:
        path = queue.pop(0)
        current = path[-1]

        if len(path) > max_depth:
            continue

        # Get sections cited by current
        cursor.execute(
            """
            SELECT DISTINCT target_identifier FROM citations
            WHERE source_identifier = ?
        """,
            (current,),
        )

        for row in cursor.fetchall():
            next_id = row[0]

            if next_id == target_identifier:
                found_paths.append(path + [next_id])
            elif next_id not in visited and len(path) < max_depth:
                visited.add(next_id)
                queue.append(path + [next_id])

    conn.close()
    return found_paths
