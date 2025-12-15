"""
Parse US Code XML files
Extracts sections, chapters, and text from USLM XML format
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict
import re

# USLM namespace
NS = {"uslm": "http://xml.house.gov/schemas/uslm/1.0"}


class USCodeSection:
    """Represents a single section of the US Code"""

    def __init__(self, identifier: str, heading: str, text: str, notes: str = ""):
        self.identifier = identifier  # e.g., "5 USC 101"
        self.heading = heading
        self.text = text
        self.notes = notes

    def to_dict(self):
        return {
            "identifier": self.identifier,
            "heading": self.heading,
            "text": self.text,
            "notes": self.notes,
        }


def clean_text(element):
    """Extract clean text from XML element"""
    if element is None:
        return ""

    # Get all text including nested elements
    text = ET.tostring(element, encoding="unicode", method="text")
    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_section(section_elem, title_num: str) -> USCodeSection:
    """Parse a single section element"""
    # Get section number from <num> element (e.g., "§ 1.")
    num_elem = section_elem.find(".//{http://xml.house.gov/schemas/uslm/1.0}num", NS)
    section_num = ""
    if num_elem is not None:
        # Extract the value attribute (e.g., "1") or text (e.g., "§ 1.")
        section_num = num_elem.get("value", "")
        if not section_num:
            section_num = clean_text(num_elem).strip("§ .").strip()

    # Build identifier like "1 USC 1", "1 USC 2", etc.
    identifier = (
        f"{title_num} USC {section_num}" if section_num else f"Title {title_num}"
    )

    # Get heading
    heading_elem = section_elem.find(
        ".//{http://xml.house.gov/schemas/uslm/1.0}heading", NS
    )
    heading = clean_text(heading_elem) if heading_elem is not None else ""

    # Get section text (all content)
    text_parts = []
    for elem in section_elem.findall(
        ".//{http://xml.house.gov/schemas/uslm/1.0}content", NS
    ):
        text_parts.append(clean_text(elem))

    text = "\n\n".join(text_parts)

    # Get notes if any
    notes_elem = section_elem.find(
        ".//{http://xml.house.gov/schemas/uslm/1.0}notes", NS
    )
    notes = clean_text(notes_elem) if notes_elem is not None else ""

    return USCodeSection(
        identifier=identifier,
        heading=heading,
        text=text,
        notes=notes,
    )


def parse_uscode_xml(xml_file: Path) -> List[USCodeSection]:
    """Parse a US Code XML file and extract all sections"""
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Get title number from <title> element's <num> child
        title_elem = root.find(
            ".//{http://xml.house.gov/schemas/uslm/1.0}title/{http://xml.house.gov/schemas/uslm/1.0}num",
            NS,
        )
        title_num = "?"
        if title_elem is not None:
            # Get the value attribute (e.g., "1")
            title_num = title_elem.get("value", "")
            if not title_num:
                # Parse from text (e.g., "Title 1—" -> "1")
                text = clean_text(title_elem)
                import re

                match = re.search(r"\d+", text)
                if match:
                    title_num = match.group(0)

        sections = []

        # Find all section elements
        for section in root.findall(
            ".//{http://xml.house.gov/schemas/uslm/1.0}section", NS
        ):
            sec = parse_section(section, title_num)
            if sec.text:  # Only include sections with content
                sections.append(sec)

        return sections

    except Exception as e:
        print(f"Error parsing {xml_file}: {e}")
        return []


def get_title_structure(xml_file: Path) -> Dict:
    """Get high-level structure of a title (chapters, subtitles)"""
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Get title info
        title_elem = root.find(".//uslm:num", NS)
        title_num = clean_text(title_elem)

        title_name_elem = root.find(".//uslm:heading", NS)
        title_name = clean_text(title_name_elem)

        # Get chapters
        chapters = []
        for chapter in root.findall(".//uslm:chapter", NS):
            chapter_num_elem = chapter.find(".//uslm:num", NS)
            chapter_heading_elem = chapter.find(".//uslm:heading", NS)

            chapters.append(
                {
                    "number": (
                        clean_text(chapter_num_elem)
                        if chapter_num_elem is not None
                        else ""
                    ),
                    "heading": (
                        clean_text(chapter_heading_elem)
                        if chapter_heading_elem is not None
                        else ""
                    ),
                }
            )

        return {"number": title_num, "name": title_name, "chapters": chapters}

    except Exception as e:
        print(f"Error getting structure from {xml_file}: {e}")
        return {}


def index_title(title_dir: Path) -> List[Dict]:
    """Index all sections in a title directory"""
    sections = []

    # Find all XML files
    for xml_file in title_dir.rglob("*.xml"):
        title_sections = parse_uscode_xml(xml_file)
        for sec in title_sections:
            sections.append(sec.to_dict())

    return sections


def search_sections(data_dir: Path, query: str, title_num: str = None) -> List[Dict]:
    """Search through US Code sections"""
    results = []
    query_lower = query.lower()

    # Determine which titles to search
    if title_num:
        title_dirs = [data_dir / f"title_{int(title_num):02d}"]
    else:
        title_dirs = [
            d for d in data_dir.iterdir() if d.is_dir() and d.name.startswith("title_")
        ]

    for title_dir in title_dirs:
        if not title_dir.exists():
            continue

        for xml_file in title_dir.rglob("*.xml"):
            sections = parse_uscode_xml(xml_file)
            for sec in sections:
                # Search in heading and text
                if (
                    query_lower in sec.heading.lower()
                    or query_lower in sec.text.lower()
                ):
                    results.append(sec.to_dict())

    return results


if __name__ == "__main__":
    # Test parsing
    data_dir = Path(__file__).parent / "data" / "uscode"

    if not data_dir.exists():
        print("No US Code data found. Run download_full_code.py first.")
    else:
        print("Testing XML parser...")

        # Find first XML file
        xml_files = list(data_dir.rglob("*.xml"))
        if xml_files:
            test_file = xml_files[0]
            print(f"\nParsing: {test_file.name}")

            sections = parse_uscode_xml(test_file)
            print(f"Found {len(sections)} sections")

            if sections:
                print(f"\nFirst section:")
                print(f"  ID: {sections[0].identifier}")
                print(f"  Heading: {sections[0].heading}")
                print(f"  Text: {sections[0].text[:200]}...")
        else:
            print("No XML files found")
