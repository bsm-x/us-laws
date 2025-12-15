"""
Citation Parser for US Code
Extracts cross-references between sections to build a citation graph.

Common citation patterns in US Code:
- "section 101 of title 17"
- "17 U.S.C. 101"
- "42 U.S.C. § 1983"
- "subsection (a) of section 102"
- "chapter 5 of this title"
- "section 101(a)(1)"

Run with: python scripts/processing/build_citation_graph.py
"""

import re
import json
import sqlite3
import sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import List, Set, Tuple, Optional
from xml.etree import ElementTree as ET

from tqdm import tqdm

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.config import get_settings

    settings = get_settings()
    DATA_DIR = settings.data_dir
    USCODE_DIR = settings.uscode_dir
except ImportError:
    DATA_DIR = PROJECT_ROOT / "data"
    USCODE_DIR = DATA_DIR / "uscode"

CITATION_DB = DATA_DIR / "citations.db"


@dataclass
class Citation:
    """Represents a citation from one section to another"""

    source_title: str
    source_section: str
    source_identifier: str
    target_title: str
    target_section: str
    target_identifier: str
    citation_text: str  # The original citation text found


# Regex patterns for different citation formats
PATTERNS = [
    # "section 101 of title 17" or "Section 101 of Title 17"
    re.compile(
        r"[Ss]ection\s+(\d+[a-z]?(?:\([a-z0-9]+\))*)\s+of\s+[Tt]itle\s+(\d+)",
        re.IGNORECASE,
    ),
    # "17 U.S.C. 101" or "17 U.S.C. § 101" or "17 USC 101"
    re.compile(
        r"(\d+)\s+U\.?S\.?C\.?\s*§?\s*(\d+[a-z]?(?:\([a-z0-9]+\))*)", re.IGNORECASE
    ),
    # "title 17, section 101"
    re.compile(
        r"[Tt]itle\s+(\d+),?\s+[Ss]ection\s+(\d+[a-z]?(?:\([a-z0-9]+\))*)",
        re.IGNORECASE,
    ),
    # "sections 101 through 105 of this title" - captures first section
    re.compile(
        r"[Ss]ections?\s+(\d+[a-z]?)\s+(?:through|to|and)\s+\d+[a-z]?\s+of\s+this\s+title",
        re.IGNORECASE,
    ),
    # "section 101 of this title"
    re.compile(
        r"[Ss]ection\s+(\d+[a-z]?(?:\([a-z0-9]+\))*)\s+of\s+this\s+title", re.IGNORECASE
    ),
]


def extract_text_from_element(element: ET.Element) -> str:
    """Recursively extract all text from an XML element"""
    texts = []
    if element.text:
        texts.append(element.text)
    for child in element:
        texts.append(extract_text_from_element(child))
        if child.tail:
            texts.append(child.tail)
    return " ".join(filter(None, texts))


def normalize_identifier(title: str, section: str) -> str:
    """Create a normalized identifier like '/us/usc/t17/s101'"""
    # Remove subsection references for the main identifier
    section_base = re.sub(r"\([a-z0-9]+\)", "", section).strip()
    return f"/us/usc/t{title}/s{section_base}"


def parse_citations(text: str, source_title: str) -> List[Tuple[str, str, str]]:
    """
    Extract citations from text.
    Returns list of (target_title, target_section, citation_text) tuples.
    """
    citations = []

    for pattern in PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groups()
            citation_text = match.group(0)

            # Different patterns have different group orders
            if (
                "of title" in citation_text.lower()
                or "of this title" in citation_text.lower()
            ):
                # Pattern: "section X of title Y" or "section X of this title"
                section = groups[0]
                if len(groups) > 1 and groups[1]:
                    title = groups[1]
                else:
                    title = source_title  # "this title" refers to current title
            elif "U.S.C" in citation_text.upper() or "USC" in citation_text.upper():
                # Pattern: "17 U.S.C. 101"
                title = groups[0]
                section = groups[1]
            elif "title" in citation_text.lower():
                # Pattern: "title 17, section 101"
                title = groups[0]
                section = groups[1]
            else:
                continue

            # Skip self-references and invalid citations
            if title and section:
                citations.append((title, section, citation_text))

    return citations


def parse_xml_for_citations(xml_path: Path) -> List[Citation]:
    """Parse a US Code XML file and extract all citations"""
    citations = []

    # Get source title from folder name
    folder_name = xml_path.parent.name
    title_match = re.search(r"title_(\d+)", folder_name)
    source_title = title_match.group(1) if title_match else "unknown"

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns_uri = "{http://xml.house.gov/schemas/uslm/1.0}"

        for section in root.iter(f"{ns_uri}section"):
            source_identifier = section.get("identifier", "")

            # Extract source section number from identifier
            sec_match = re.search(r"/s(\d+[a-z]?)", source_identifier)
            source_section = sec_match.group(1) if sec_match else ""

            # Get full text of section
            text = extract_text_from_element(section)

            # Find citations
            found_citations = parse_citations(text, source_title)

            for target_title, target_section, citation_text in found_citations:
                target_identifier = normalize_identifier(target_title, target_section)

                # Skip self-citations
                if target_identifier == source_identifier:
                    continue

                citations.append(
                    Citation(
                        source_title=source_title,
                        source_section=source_section,
                        source_identifier=source_identifier,
                        target_title=target_title,
                        target_section=target_section,
                        target_identifier=target_identifier,
                        citation_text=citation_text,
                    )
                )

    except ET.ParseError as e:
        print(f"  Warning: Failed to parse {xml_path.name}: {e}")
    except Exception as e:
        print(f"  Warning: Error processing {xml_path.name}: {e}")

    return citations


def create_database(citations: List[Citation]):
    """Create SQLite database with citation graph"""
    print(f"\nCreating database at {CITATION_DB}...")

    conn = sqlite3.connect(CITATION_DB)
    cursor = conn.cursor()

    # Create tables
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_title TEXT,
            source_section TEXT,
            source_identifier TEXT,
            target_title TEXT,
            target_section TEXT,
            target_identifier TEXT,
            citation_text TEXT,
            UNIQUE(source_identifier, target_identifier, citation_text)
        )
    """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_source ON citations(source_identifier)
    """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_target ON citations(target_identifier)
    """
    )

    # Insert citations
    inserted = 0
    for c in citations:
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO citations
                (source_title, source_section, source_identifier,
                 target_title, target_section, target_identifier, citation_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    c.source_title,
                    c.source_section,
                    c.source_identifier,
                    c.target_title,
                    c.target_section,
                    c.target_identifier,
                    c.citation_text,
                ),
            )
            if cursor.rowcount > 0:
                inserted += 1
        except sqlite3.Error as e:
            pass

    conn.commit()

    # Get stats
    cursor.execute("SELECT COUNT(*) FROM citations")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT source_identifier) FROM citations")
    sources = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT target_identifier) FROM citations")
    targets = cursor.fetchone()[0]

    conn.close()

    return total, sources, targets


def build_citation_graph():
    """Main function to build the citation graph"""
    print("=" * 60)
    print("CITATION GRAPH BUILDER")
    print("=" * 60)
    print(f"US Code directory: {USCODE_DIR}")
    print(f"Output database: {CITATION_DB}")

    # Find all XML files
    xml_files = sorted(USCODE_DIR.rglob("*.xml"))

    if not xml_files:
        print("ERROR: No XML files found!")
        return

    print(f"\nFound {len(xml_files)} XML files")

    # Parse all files
    all_citations = []

    for xml_file in tqdm(xml_files, desc="Parsing citations"):
        citations = parse_xml_for_citations(xml_file)
        all_citations.extend(citations)

    print(f"\nFound {len(all_citations):,} total citations")

    # Deduplicate
    seen = set()
    unique_citations = []
    for c in all_citations:
        key = (c.source_identifier, c.target_identifier)
        if key not in seen:
            seen.add(key)
            unique_citations.append(c)

    print(f"Unique citation relationships: {len(unique_citations):,}")

    # Create database
    total, sources, targets = create_database(all_citations)

    print("\n" + "-" * 60)
    print("CITATION GRAPH COMPLETE")
    print("-" * 60)
    print(f"Total citations: {total:,}")
    print(f"Sections that cite others: {sources:,}")
    print(f"Sections that are cited: {targets:,}")
    print(f"Database: {CITATION_DB}")

    # Show top cited sections
    print("\n" + "-" * 60)
    print("TOP 10 MOST CITED SECTIONS:")
    print("-" * 60)

    conn = sqlite3.connect(CITATION_DB)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT target_identifier, COUNT(*) as cnt
        FROM citations
        GROUP BY target_identifier
        ORDER BY cnt DESC
        LIMIT 10
    """
    )

    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} citations")

    conn.close()


if __name__ == "__main__":
    build_citation_graph()
