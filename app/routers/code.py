"""
US Code browser router
"""

import re
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.templates import render_page
from app.data_loaders import load_titles
from app.config import get_settings
from scripts.processing.parse_uscode import (
    parse_uscode_xml,
    get_title_structure,
)

router = APIRouter(tags=["code"])
settings = get_settings()

# Get paths from config
USCODE_DIR = settings.uscode_dir


def format_section_text(text: str) -> str:
    """Format section text with proper HTML structure"""
    if not text:
        return ""

    lines = text.split("\n")
    formatted = []
    in_list = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                formatted.append("</ul>")
                in_list = False
            continue

        # Check if line looks like a list item (starts with letter/number followed by parenthesis or period)
        if re.match(r"^[\(]?[a-z0-9]+[\)\.]\s", line, re.IGNORECASE):
            if not in_list:
                formatted.append('<ul style="margin: 1rem 0; padding-left: 2rem;">')
                in_list = True
            formatted.append(f'<li style="margin: 0.5rem 0;">{line}</li>')
        else:
            if in_list:
                formatted.append("</ul>")
                in_list = False
            formatted.append(f'<p style="margin: 1rem 0;">{line}</p>')

    if in_list:
        formatted.append("</ul>")

    return "".join(formatted)


@router.get("/code", response_class=HTMLResponse)
async def code_structure():
    """View US Code structure"""
    titles = load_titles()

    rows = ""
    for title in titles:
        enacted = title.get("Enacted as Positive Law", "") == "Yes"
        tag = (
            '<span class="tag enacted">Enacted</span>'
            if enacted
            else '<span class="tag">Not Enacted</span>'
        )
        title_num = title.get("Title Number", "")
        rows += f"""
        <tr>
            <td>{title_num}</td>
            <td>{title.get('Title Name', '')}</td>
            <td>{tag}</td>
            <td><a href="/code/{title_num}">View →</a></td>
        </tr>
        """

    content = f"""
    <h1>US Code Structure</h1>
    <p>The United States Code organizes all federal statutes into 54 subject titles.</p>

    <div class="stats">
        <div class="stat-card">
            <div class="number">{len(titles)}</div>
            <div class="label">Total Titles</div>
        </div>
        <div class="stat-card">
            <div class="number">{sum(1 for t in titles if t.get('Enacted as Positive Law') == 'Yes')}</div>
            <div class="label">Enacted as Positive Law</div>
        </div>
    </div>

    <h2>All Titles</h2>
    <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th style="width: 80px;">#</th>
                    <th>Title Name</th>
                    <th style="width: 120px;">Status</th>
                    <th style="width: 100px;">View</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>

    <h2>About the US Code</h2>
    <p>
        <strong>Enacted as Positive Law</strong> means the title itself has been enacted by Congress
        and is legal evidence of the law. Non-enacted titles are organized compilations where the
        underlying statutes (Statutes at Large) are the actual legal authority.
    </p>
    <p style="margin-top: 1rem;">
        <a href="https://uscode.house.gov/" target="_blank">Official US Code →</a>
    </p>
    """

    return render_page("US Code", content, "code")


@router.get("/code/{title_num}", response_class=HTMLResponse)
async def view_title(title_num: int, search: str = Query("")):
    """View a specific US Code title"""
    if USCODE_DIR is None:
        content = """
        <h1>Configuration Error</h1>
        <p>US Code directory is not configured.</p>
        <p><a href="/code">← Back to all titles</a></p>
        """
        return render_page(f"Title {title_num}", content, "code")

    title_dir = USCODE_DIR / f"title_{title_num:02d}"

    if not title_dir.exists():
        content = f"""
        <h1>Title {title_num} Not Downloaded</h1>
        <p>This title hasn't been downloaded yet.</p>
        <p><a href="/code">← Back to all titles</a></p>
        <h2>To download:</h2>
        <pre>python scripts/download/download_full_code.py</pre>
        """
        return render_page(f"Title {title_num}", content, "code")

    # Get sections
    xml_files = list(title_dir.rglob("*.xml"))
    if not xml_files:
        content = f"""
        <h1>Title {title_num} - No Data</h1>
        <p>No XML files found in this title.</p>
        <p><a href="/code">← Back to all titles</a></p>
        """
        return render_page(f"Title {title_num}", content, "code")

    # Parse first XML file to get structure
    structure = get_title_structure(xml_files[0])
    title_name = structure.get("name", f"Title {title_num}")

    # Get all sections
    all_sections = []
    for xml_file in xml_files[:5]:  # Limit to first 5 files for performance
        sections = parse_uscode_xml(xml_file)
        all_sections.extend(sections)

    # Filter by search
    if search:
        search_lower = search.lower()
        all_sections = [
            s
            for s in all_sections
            if search_lower in s.heading.lower() or search_lower in s.text.lower()
        ]

    # Build sections HTML with collapsible sections
    sections_html = ""
    for idx, sec in enumerate(all_sections[:50]):  # Show first 50
        formatted_text = format_section_text(sec.text)
        sections_html += f"""
        <div class="section-item" style="border-bottom: 1px solid #30363d; padding: 1rem 0;">
            <div class="section-header" onclick="toggleSection({idx})" style="cursor: pointer; display: flex; align-items: center; gap: 0.5rem;">
                <span class="toggle-icon" id="toggle-{idx}" style="font-weight: bold; color: #58a6ff;">▼</span>
                <div style="flex: 1;">
                    <h3 style="margin: 0; color: #58a6ff; font-size: 1.1rem; display: inline;">{sec.identifier}</h3>
                    <span style="color: #c9d1d9; font-weight: normal; margin-left: 0.5rem;">— {sec.heading}</span>
                </div>
            </div>
            <div class="section-content" id="content-{idx}" style="margin-top: 1rem; padding-left: 1.5rem; line-height: 1.8; color: #c9d1d9;">
                {formatted_text}
            </div>
        </div>
        """

    if not sections_html:
        sections_html = "<p>No sections found.</p>"

    content = f"""
    <style>
        .section-item {{ transition: background 0.2s; }}
        .section-item:hover {{ background: #21262d; }}
        .section-content {{ display: block; }}
        .section-content.collapsed {{ display: none; }}
    </style>

    <script>
        function toggleSection(id) {{
            const content = document.getElementById('content-' + id);
            const toggle = document.getElementById('toggle-' + id);
            content.classList.toggle('collapsed');
            toggle.textContent = content.classList.contains('collapsed') ? '▶' : '▼';
        }}

        function collapseAll() {{
            document.querySelectorAll('.section-content').forEach((el, idx) => {{
                el.classList.add('collapsed');
                document.getElementById('toggle-' + idx).textContent = '▶';
            }});
        }}

        function expandAll() {{
            document.querySelectorAll('.section-content').forEach((el, idx) => {{
                el.classList.remove('collapsed');
                document.getElementById('toggle-' + idx).textContent = '▼';
            }});
        }}
    </script>

    <p><a href="/code">← Back to all titles</a></p>
    <h1>Title {title_num}: {title_name}</h1>

    <form class="search-box" method="get">
        <input type="text" name="search" placeholder="Search this title..." value="{search}">
        <button type="submit">Search</button>
    </form>

    <div style="margin: 1rem 0; display: flex; gap: 1rem; align-items: center;">
        <p style="margin: 0;">Showing {min(len(all_sections), 50)} of {len(all_sections)} sections</p>
        <button onclick="collapseAll()" style="padding: 0.5rem 1rem; cursor: pointer; background: #21262d; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px;">Collapse All</button>
        <button onclick="expandAll()" style="padding: 0.5rem 1rem; cursor: pointer; background: #21262d; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px;">Expand All</button>
    </div>

    <div class="card">
        {sections_html}
    </div>
    """

    return render_page(f"Title {title_num}", content, "code")
