"""
Simple web viewer for US Laws and Code
Run with: python app.py
Then visit: http://localhost:8000
"""

import csv
import os
from pathlib import Path
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from parse_uscode import parse_uscode_xml, search_sections, get_title_structure
from dotenv import load_dotenv
import markdown

# Load environment variables
load_dotenv()

app = FastAPI(title="US Laws Viewer")

# Data directory
DATA_DIR = Path(__file__).parent
USCODE_DIR = DATA_DIR / "data" / "uscode"
VECTOR_DB_DIR = DATA_DIR / "data" / "vector_db"

# Vector database client (lazy loaded)
_vector_client = None
_vector_collection = None

# Cache for loaded data
_laws_cache = None
_titles_cache = None
_uscode_cache = {}


def load_laws():
    """Load laws from CSV"""
    global _laws_cache
    if _laws_cache is not None:
        return _laws_cache

    laws = []
    csv_path = DATA_DIR / "us_public_laws.csv"
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                laws.append(row)
    _laws_cache = laws
    return laws


def load_titles():
    """Load US Code titles from CSV"""
    global _titles_cache
    if _titles_cache is not None:
        return _titles_cache

    titles = []
    csv_path = DATA_DIR / "us_code_titles.csv"
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                titles.append(row)
    _titles_cache = titles
    return titles


# HTML Template
def render_page(title: str, content: str, nav_active: str = ""):
    """Render a page with the common layout"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - US Laws Viewer</title>
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        nav {{
            background: #1a365d;
            padding: 1rem 2rem;
            display: flex;
            gap: 2rem;
            align-items: center;
        }}
        nav a {{
            color: #fff;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            transition: background 0.2s;
        }}
        nav a:hover, nav a.active {{
            background: #2c5282;
        }}
        nav .logo {{
            font-weight: bold;
            font-size: 1.2rem;
            margin-right: auto;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}
        h1 {{ margin-bottom: 1rem; color: #1a365d; }}
        h2 {{ margin: 1.5rem 0 1rem; color: #2c5282; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat-card {{
            background: #fff;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-card .number {{
            font-size: 2.5rem;
            font-weight: bold;
            color: #2c5282;
        }}
        .stat-card .label {{
            color: #666;
            font-size: 0.9rem;
        }}
        table {{
            width: 100%;
            background: #fff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-collapse: collapse;
        }}
        th, td {{
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #1a365d;
            position: sticky;
            top: 0;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .search-box {{
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }}
        .search-box input, .search-box select {{
            padding: 0.75rem 1rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 1rem;
        }}
        .search-box input {{
            flex: 1;
            min-width: 200px;
        }}
        .search-box button {{
            padding: 0.75rem 1.5rem;
            background: #2c5282;
            color: #fff;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1rem;
        }}
        .search-box button:hover {{
            background: #1a365d;
        }}
        .pagination {{
            display: flex;
            gap: 0.5rem;
            margin-top: 1rem;
            justify-content: center;
        }}
        .pagination a {{
            padding: 0.5rem 1rem;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
            text-decoration: none;
            color: #333;
        }}
        .pagination a:hover, .pagination a.active {{
            background: #2c5282;
            color: #fff;
            border-color: #2c5282;
        }}
        .tag {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            background: #e2e8f0;
            border-radius: 4px;
            font-size: 0.8rem;
            color: #4a5568;
        }}
        .tag.enacted {{
            background: #c6f6d5;
            color: #276749;
        }}
        .table-wrapper {{
            overflow-x: auto;
            max-height: 70vh;
            overflow-y: auto;
        }}
        .chart {{
            background: #fff;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }}
        .bar {{
            display: flex;
            align-items: center;
            margin: 0.25rem 0;
        }}
        .bar-label {{
            width: 120px;
            font-size: 0.85rem;
        }}
        .bar-fill {{
            height: 20px;
            background: #3182ce;
            border-radius: 2px;
            transition: width 0.3s;
        }}
        .bar-value {{
            margin-left: 0.5rem;
            font-size: 0.85rem;
            color: #666;
        }}
    </style>
</head>
<body>
    <nav>
        <span class="logo">📜 US Laws Viewer</span>
        <a href="/" class="{'active' if nav_active == 'home' else ''}">Home</a>
        <a href="/laws" class="{'active' if nav_active == 'laws' else ''}">Public Laws</a>
        <a href="/code" class="{'active' if nav_active == 'code' else ''}">US Code</a>
        <a href="/search" class="{'active' if nav_active == 'search' else ''}">🔍 Search</a>
        <a href="/ask" class="{'active' if nav_active == 'ask' else ''}">💬 Ask AI</a>
    </nav>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def home():
    """Home page with overview"""
    laws = load_laws()
    titles = load_titles()

    # Calculate stats
    total_laws = len(laws)

    # Laws by congress
    by_congress = {}
    for law in laws:
        c = law.get("Congress", "")
        if c:
            by_congress[int(c)] = by_congress.get(int(c), 0) + 1

    # Build chart
    max_count = max(by_congress.values()) if by_congress else 1
    chart_html = ""
    for congress in sorted(by_congress.keys()):
        year = 1789 + (congress - 1) * 2
        count = by_congress[congress]
        width = (count / max_count) * 100
        chart_html += f"""
        <div class="bar">
            <span class="bar-label">{congress} ({year})</span>
            <div class="bar-fill" style="width: {width}%"></div>
            <span class="bar-value">{count}</span>
        </div>
        """

    # Check if vector DB exists
    has_vector_db = VECTOR_DB_DIR.exists()

    content = f"""
    <h1>US Federal Law Overview</h1>

    {f'''
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 12px; margin: 2rem 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0 0 1rem;">🔍 AI-Powered Semantic Search</h2>
        <p style="color: rgba(255,255,255,0.9); margin-bottom: 1.5rem;">Ask questions in natural language and find relevant sections across all 60,000+ sections of the US Code.</p>
        <form action="/search" method="get" style="display: flex; gap: 1rem;">
            <input type="text" name="q" placeholder="e.g., 'copyright protection duration' or 'criminal penalties for fraud'"
                   style="flex: 1; padding: 1rem; border: none; border-radius: 8px; font-size: 1rem;">
            <button type="submit" style="background: white; color: #667eea; padding: 1rem 2rem; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 1rem;">
                Search
            </button>
        </form>
        <p style="color: rgba(255,255,255,0.8); font-size: 0.85rem; margin-top: 1rem;">
            ⚡ Powered by OpenAI text-embedding-3-large
        </p>
    </div>
    ''' if has_vector_db else f'''
    <div style="background: #fff3cd; padding: 1.5rem; border-radius: 8px; margin: 2rem 0; border-left: 4px solid #ffc107;">
        <h3 style="margin: 0 0 0.5rem;">💡 Want AI-powered search?</h3>
        <p style="margin: 0.5rem 0;">Create a vector database to enable semantic search across all US Code sections.</p>
        <a href="/search" style="display: inline-block; margin-top: 0.5rem; color: #0066cc;">Learn more →</a>
    </div>
    '''}

    <div class="stats">
        <div class="stat-card">
            <div class="number">{total_laws:,}</div>
            <div class="label">Public Laws (1951-2024)</div>
        </div>
        <div class="stat-card">
            <div class="number">{len(titles)}</div>
            <div class="label">US Code Titles</div>
        </div>
        <div class="stat-card">
            <div class="number">~60,000</div>
            <div class="label">Code Sections</div>
        </div>
        <div class="stat-card">
            <div class="number">{len(by_congress)}</div>
            <div class="label">Congresses Covered</div>
        </div>
    </div>

    <h2>Laws by Congress</h2>
    <div class="chart">
        {chart_html}
    </div>

    <h2>Quick Links</h2>
    <p>
        <a href="/laws">Browse all {total_laws:,} public laws →</a><br>
        <a href="/code">View US Code structure →</a>
    </p>
    """

    return render_page("Home", content, "home")


@app.get("/laws", response_class=HTMLResponse)
async def laws_list(
    page: int = Query(1, ge=1), search: str = Query(""), congress: str = Query("")
):
    """Browse public laws"""
    laws = load_laws()

    # Filter
    filtered = laws
    if search:
        search_lower = search.lower()
        filtered = [
            l
            for l in filtered
            if search_lower in l.get("Title", "").lower()
            or search_lower in l.get("Public Law", "").lower()
        ]
    if congress:
        filtered = [l for l in filtered if l.get("Congress") == congress]

    # Paginate
    per_page = 100
    total = len(filtered)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    page_laws = filtered[start:end]

    # Get unique congresses for filter
    congresses = sorted(
        set(l.get("Congress", "") for l in laws if l.get("Congress")),
        key=lambda x: int(x) if x.isdigit() else 0,
        reverse=True,
    )

    # Build congress options
    congress_options = '<option value="">All Congresses</option>'
    for c in congresses:
        selected = "selected" if c == congress else ""
        year = 1789 + (int(c) - 1) * 2 if c.isdigit() else ""
        congress_options += f'<option value="{c}" {selected}>{c} ({year})</option>'

    # Build table
    rows = ""
    for law in page_laws:
        rows += f"""
        <tr>
            <td>{law.get('Congress', '')}</td>
            <td>{law.get('Public Law', '')}</td>
            <td>{law.get('Title', '')[:100]}{'...' if len(law.get('Title', '')) > 100 else ''}</td>
            <td>{law.get('Origin Chamber', '')}</td>
            <td>{law.get('Latest Action Date', '')}</td>
        </tr>
        """

    # Pagination
    pagination = ""
    if total_pages > 1:
        base_url = f"/laws?search={search}&congress={congress}"
        if page > 1:
            pagination += f'<a href="{base_url}&page={page-1}">← Prev</a>'
        pagination += (
            f'<span style="padding: 0.5rem;">Page {page} of {total_pages}</span>'
        )
        if page < total_pages:
            pagination += f'<a href="{base_url}&page={page+1}">Next →</a>'

    content = f"""
    <h1>Public Laws</h1>
    <p>Showing {len(page_laws):,} of {total:,} laws</p>

    <form class="search-box" method="get">
        <input type="text" name="search" placeholder="Search by title or law number..." value="{search}">
        <select name="congress">
            {congress_options}
        </select>
        <button type="submit">Search</button>
    </form>

    <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Congress</th>
                    <th>Public Law</th>
                    <th>Title</th>
                    <th>Origin</th>
                    <th>Date</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>

    <div class="pagination">
        {pagination}
    </div>
    """

    return render_page("Public Laws", content, "laws")


@app.get("/code", response_class=HTMLResponse)
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


@app.get("/code/{title_num}", response_class=HTMLResponse)
async def view_title(title_num: int, search: str = Query("")):
    """View a specific US Code title"""
    title_dir = USCODE_DIR / f"title_{title_num:02d}"

    if not title_dir.exists():
        content = f"""
        <h1>Title {title_num} Not Downloaded</h1>
        <p>This title hasn't been downloaded yet.</p>
        <p><a href="/code">← Back to all titles</a></p>
        <h2>To download:</h2>
        <pre>python download_full_code.py</pre>
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

    # Format section text with proper lists and structure
    def format_section_text(text):
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
            import re

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

    # Build sections HTML in one long container with collapsible sections
    sections_html = ""
    for idx, sec in enumerate(all_sections[:50]):  # Show first 50
        formatted_text = format_section_text(sec.text)
        sections_html += f"""
        <div class="section-item" style="border-bottom: 1px solid #e2e8f0; padding: 1rem 0;">
            <div class="section-header" onclick="toggleSection({idx})" style="cursor: pointer; display: flex; align-items: center; gap: 0.5rem;">
                <span class="toggle-icon" id="toggle-{idx}" style="font-weight: bold; color: #2c5282;">▼</span>
                <div style="flex: 1;">
                    <h3 style="margin: 0; color: #2c5282; font-size: 1.1rem; display: inline;">{sec.identifier}</h3>
                    <span style="color: #4a5568; font-weight: normal; margin-left: 0.5rem;">— {sec.heading}</span>
                </div>
            </div>
            <div class="section-content" id="content-{idx}" style="margin-top: 1rem; padding-left: 1.5rem; line-height: 1.8; color: #333;">
                {formatted_text}
            </div>
        </div>
        """

    if not sections_html:
        sections_html = "<p>No sections found.</p>"

    content = f"""
    <style>
        .section-item {{ transition: background 0.2s; }}
        .section-item:hover {{ background: #f7fafc; }}
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
        <button onclick="collapseAll()" style="padding: 0.5rem 1rem; cursor: pointer;">Collapse All</button>
        <button onclick="expandAll()" style="padding: 0.5rem 1rem; cursor: pointer;">Expand All</button>
    </div>

    <div style="background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-top: 1rem;">
        {sections_html}
    </div>
    """

    return render_page(f"Title {title_num}", content, "code")


@app.get("/search", response_class=HTMLResponse)
async def semantic_search(q: str = Query("")):
    """Semantic search across all US Code"""
    global _vector_client, _vector_collection

    # Check if vector DB exists
    if not VECTOR_DB_DIR.exists():
        content = """
        <h1>🔍 Semantic Search</h1>
        <div style="background: #fff3cd; padding: 1.5rem; border-radius: 8px; margin: 2rem 0;">
            <h3>⚠️ Vector Database Not Created</h3>
            <p>To use semantic search, you need to create the vector database first:</p>
            <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; margin: 1rem 0;">pip install chromadb
python create_vector_db.py</pre>
            <p>This will embed all US Code sections for semantic search (~10-30 minutes).</p>
        </div>
        <h2>What is Semantic Search?</h2>
        <p>Semantic search understands the <em>meaning</em> of your query, not just keywords.</p>
        <p><strong>Examples:</strong></p>
        <ul>
            <li>"copyright protection duration" - finds relevant sections about copyright law</li>
            <li>"criminal penalties for fraud" - finds fraud-related criminal statutes</li>
            <li>"tax deductions for businesses" - finds business tax provisions</li>
            <li>"workplace discrimination rules" - finds employment discrimination laws</li>
        </ul>
        """
        return render_page("Semantic Search", content, "search")

    # Load vector DB
    if _vector_client is None:
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            # Get OpenAI API key
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                content = """
                <h1>🔍 Semantic Search</h1>
                <div style="background: #ffe4e1; padding: 1.5rem; border-radius: 8px; margin: 2rem 0;">
                    <h3>❌ OpenAI API Key Not Found</h3>
                    <p>The vector database uses OpenAI embeddings, but the API key is missing.</p>
                    <p>Add your API key to the <code>.env</code> file:</p>
                    <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; margin: 1rem 0;">OPENAI_API_KEY=sk-proj-your-key-here</pre>
                </div>
                """
                return render_page("Semantic Search", content, "search")

            # Create OpenAI embedding function
            openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=api_key, model_name="text-embedding-3-large"
            )

            _vector_client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
            _vector_collection = _vector_client.get_collection(
                name="uscode", embedding_function=openai_ef
            )
        except Exception as e:
            content = f"""
            <h1>🔍 Semantic Search</h1>
            <div style="background: #ffe4e1; padding: 1.5rem; border-radius: 8px; margin: 2rem 0;">
                <h3>❌ Error Loading Vector Database</h3>
                <p>{str(e)}</p>
                <p>Try installing chromadb: <code>pip install chromadb</code></p>
            </div>
            """
            return render_page("Semantic Search", content, "search")

    # Search form
    form_html = f"""
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
        <h1 style="margin: 0;">🔍 Semantic Search</h1>
        <span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: bold;">
            ⚡ OpenAI Powered
        </span>
    </div>
    <p style="margin-bottom: 2rem;">Search the entire US Code using natural language. The AI understands meaning and context, not just keywords.</p>

    <form class="search-box" method="get" style="margin: 2rem 0;">
        <input type="text" name="q" placeholder="e.g., 'copyright protection duration' or 'criminal penalties for fraud'" value="{q}" style="flex: 1;" autofocus>
        <button type="submit">Search</button>
    </form>
    """

    if not q:
        # Show examples
        examples_html = """
        <div style="background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h2>Example Queries</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin-top: 1rem;">
                <div style="padding: 1rem; background: #f7fafc; border-radius: 4px;">
                    <strong>💼 Business & Tax</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        <li><a href="/search?q=tax+deductions+for+home+offices">tax deductions for home offices</a></li>
                        <li><a href="/search?q=corporate+tax+rates">corporate tax rates</a></li>
                        <li><a href="/search?q=business+expense+deductions">business expense deductions</a></li>
                    </ul>
                </div>
                <div style="padding: 1rem; background: #f7fafc; border-radius: 4px;">
                    <strong>⚖️ Criminal Law</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        <li><a href="/search?q=penalties+for+insider+trading">penalties for insider trading</a></li>
                        <li><a href="/search?q=wire+fraud+statutes">wire fraud statutes</a></li>
                        <li><a href="/search?q=computer+crime+laws">computer crime laws</a></li>
                    </ul>
                </div>
                <div style="padding: 1rem; background: #f7fafc; border-radius: 4px;">
                    <strong>📚 Intellectual Property</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        <li><a href="/search?q=copyright+protection+duration">copyright protection duration</a></li>
                        <li><a href="/search?q=patent+infringement+remedies">patent infringement remedies</a></li>
                        <li><a href="/search?q=trademark+registration">trademark registration</a></li>
                    </ul>
                </div>
                <div style="padding: 1rem; background: #f7fafc; border-radius: 4px;">
                    <strong>👥 Employment & Civil Rights</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        <li><a href="/search?q=workplace+discrimination+laws">workplace discrimination laws</a></li>
                        <li><a href="/search?q=minimum+wage+requirements">minimum wage requirements</a></li>
                        <li><a href="/search?q=disability+accommodations">disability accommodations</a></li>
                    </ul>
                </div>
            </div>
        </div>
        """
        content = form_html + examples_html
        return render_page("Semantic Search", content, "search")

    # Perform search
    try:
        results = _vector_collection.query(query_texts=[q], n_results=15)

        if not results["documents"][0]:
            results_html = "<p>No results found. Try a different query.</p>"
        else:
            results_html = f"""
            <style>
                .search-result {{ transition: background 0.2s; }}
                .search-result:hover {{ background: #f7fafc; }}
                .result-content {{ display: block; }}
                .result-content.collapsed {{ display: none; }}
            </style>

            <script>
                function toggleResult(id) {{
                    const content = document.getElementById('result-' + id);
                    const toggle = document.getElementById('toggle-' + id);
                    content.classList.toggle('collapsed');
                    toggle.textContent = content.classList.contains('collapsed') ? '▶ Show more' : '▼ Show less';
                }}
            </script>

            <div style="margin: 1rem 0; display: flex; align-items: center; gap: 1rem;">
                <p style="margin: 0; font-weight: bold;">Found {len(results['documents'][0])} relevant sections</p>
                <span style="color: #666; font-size: 0.9rem;">Powered by text-embedding-3-large</span>
            </div>
            <div style='background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);'>"""

            for i, (doc, meta, distance) in enumerate(
                zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )
            ):
                relevance = (1 - distance) * 100

                # Extract text
                text_start = doc.find("\n\n")
                if text_start > 0:
                    text = doc[text_start + 2 :]
                else:
                    text = doc

                preview = text[:400].strip()
                if len(text) > 400:
                    preview += "..."

                # Extract title number for link
                title_match = (
                    meta["identifier"].split(" ")[0]
                    if " " in meta["identifier"]
                    else None
                )

                results_html += f"""
                <div class="search-result" style="border-bottom: 1px solid #e2e8f0; padding: 1.5rem 0;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                        <div style="display: flex; align-items: center; gap: 1rem;">
                            <span style="background: #e6f2ff; color: #0066cc; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: bold;">
                                {relevance:.0f}% match
                            </span>
                            <h3 style="margin: 0; color: #2c5282; font-size: 1.1rem;">{meta['identifier']}</h3>
                        </div>
                        {f'<a href="/code/{title_match}" style="color: #0066cc; text-decoration: none; font-size: 0.9rem;">View in context →</a>' if title_match and title_match.isdigit() else ''}
                    </div>
                    <h4 style="margin: 0.5rem 0 1rem; color: #4a5568; font-weight: normal;">{meta['heading']}</h4>
                    <div id="result-{i}" class="result-content">
                        <p style="line-height: 1.8; color: #333; white-space: pre-wrap;">{text if len(text) <= 800 else text[:800] + '...'}</p>
                    </div>
                    <button onclick="toggleResult({i})" id="toggle-{i}" style="margin-top: 0.5rem; padding: 0.25rem 0.75rem; background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">
                        {('▶ Show more' if len(text) > 800 else '')}
                    </button>
                </div>
                """

            results_html += "</div>"

        content = form_html + results_html

    except Exception as e:
        content = (
            form_html
            + f"""
        <div style="background: #ffe4e1; padding: 1.5rem; border-radius: 8px; margin: 2rem 0;">
            <h3>❌ Search Error</h3>
            <p>{str(e)}</p>
        </div>
        """
        )

    return render_page("Semantic Search", content, "search")


@app.get("/ask", response_class=HTMLResponse)
async def ask_ai(q: str = Query(""), provider: str = Query("openai")):
    """RAG: Ask questions and get AI-generated answers"""

    # Check if vector DB exists
    if not VECTOR_DB_DIR.exists():
        content = """
        <h1><span class="material-icons" style="vertical-align: middle;">chat</span> Ask AI About US Code</h1>
        <div style="background: #fff3cd; padding: 1.5rem; border-radius: 8px; margin: 2rem 0;">
            <h3><span class="material-icons" style="vertical-align: middle;">warning</span> Vector Database Required</h3>
            <p>To use AI Q&A, create the vector database first:</p>
            <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; margin: 1rem 0;">python create_vector_db.py</pre>
        </div>
        """
        return render_page("Ask AI", content, "ask")

    # Form HTML
    form_html = f"""
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
        <h1 style="margin: 0; display: flex; align-items: center; gap: 0.5rem;"><span class="material-icons" style="font-size: 2rem;">chat</span> Ask Questions About US Code</h1>
        <span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: bold;">
            RAG Powered
        </span>
    </div>
    <p style="margin-bottom: 2rem;">Ask natural language questions and get AI-generated answers based on actual US Code sections.</p>

    <form class="search-box" method="get" style="margin: 2rem 0;">
        <input type="text" name="q" placeholder="e.g., 'How long does copyright protection last?'" value="{q}" style="flex: 1;" autofocus>
        <select name="provider" style="padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; font-size: 1rem;">
            <option value="openai" {"selected" if provider == "openai" else ""}>GPT-4</option>
            <option value="anthropic" {"selected" if provider == "anthropic" else ""}>Claude</option>
        </select>
        <button type="submit">Ask</button>
    </form>
    """

    if not q:
        # Show examples
        examples_html = """
        <div style="background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h2>Example Questions</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin-top: 1rem;">
                <div style="padding: 1rem; background: #f7fafc; border-radius: 4px;">
                    <strong><span class="material-icons" style="vertical-align: middle; font-size: 1.2rem;">book</span> Copyright & IP</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        <li><a href="/ask?q=How+long+does+copyright+protection+last">How long does copyright protection last?</a></li>
                        <li><a href="/ask?q=What+is+fair+use+under+copyright+law">What is fair use under copyright law?</a></li>
                        <li><a href="/ask?q=How+do+I+register+a+patent">How do I register a patent?</a></li>
                    </ul>
                </div>
                <div style="padding: 1rem; background: #f7fafc; border-radius: 4px;">
                    <strong><span class="material-icons" style="vertical-align: middle; font-size: 1.2rem;">business</span> Business & Tax</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        <li><a href="/ask?q=Can+I+deduct+home+office+expenses">Can I deduct home office expenses?</a></li>
                        <li><a href="/ask?q=What+is+the+corporate+tax+rate">What is the corporate tax rate?</a></li>
                        <li><a href="/ask?q=How+are+capital+gains+taxed">How are capital gains taxed?</a></li>
                    </ul>
                </div>
                <div style="padding: 1rem; background: #f7fafc; border-radius: 4px;">
                    <strong><span class="material-icons" style="vertical-align: middle; font-size: 1.2rem;">gavel</span> Criminal Law</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        <li><a href="/ask?q=What+are+penalties+for+wire+fraud">What are penalties for wire fraud?</a></li>
                        <li><a href="/ask?q=What+constitutes+insider+trading">What constitutes insider trading?</a></li>
                        <li><a href="/ask?q=What+are+federal+drug+laws">What are federal drug laws?</a></li>
                    </ul>
                </div>
                <div style="padding: 1rem; background: #f7fafc; border-radius: 4px;">
                    <strong><span class="material-icons" style="vertical-align: middle; font-size: 1.2rem;">people</span> Employment</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem;">
                        <li><a href="/ask?q=What+is+the+federal+minimum+wage">What is the federal minimum wage?</a></li>
                        <li><a href="/ask?q=What+workplace+discrimination+is+illegal">What workplace discrimination is illegal?</a></li>
                        <li><a href="/ask?q=What+are+FMLA+leave+requirements">What are FMLA leave requirements?</a></li>
                    </ul>
                </div>
            </div>

            <div style="margin-top: 2rem; padding: 1.5rem; background: #e6f7ff; border-radius: 4px; border-left: 4px solid #1890ff;">
                <h3 style="margin: 0 0 0.5rem;">How RAG Works</h3>
                <ol style="margin: 0.5rem 0; padding-left: 1.5rem;">
                    <li><strong>Retrieve:</strong> Searches vector database for relevant US Code sections</li>
                    <li><strong>Augment:</strong> Adds those sections as context to your question</li>
                    <li><strong>Generate:</strong> AI generates an answer based only on retrieved sections</li>
                </ol>
                <p style="margin: 0.5rem 0 0; font-size: 0.9rem; color: #666;">
                    Answers are grounded in actual law, with citations to specific sections.
                </p>
            </div>
        </div>
        """
        content = form_html + examples_html
        return render_page("Ask AI", content, "ask")

    # Process question
    try:
        from rag import get_relevant_sections, answer_with_openai, answer_with_anthropic

        # Retrieve sections
        sections = get_relevant_sections(q, n_results=5)

        if not sections:
            result_html = "<p>No relevant sections found to answer this question.</p>"
        else:
            # Generate answer
            if provider == "anthropic":
                answer = answer_with_anthropic(q, sections)
                model_name = "Claude Sonnet 4"
            else:
                answer = answer_with_openai(q, sections)
                model_name = "GPT-4o"

            # Format answer with sources
            # Convert markdown to HTML
            answer_html = markdown.markdown(answer, extensions=["extra", "nl2br"])

            result_html = f"""
            <div style="background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-top: 2rem;">
                <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                    <h2 style="margin: 0;">Answer</h2>
                    <span style="background: #e6f2ff; color: #0066cc; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: bold;">
                        {model_name}
                    </span>
                </div>
                <div style="line-height: 1.8; color: #333; padding: 1rem; background: #f7fafc; border-radius: 4px;">
{answer_html}
                </div>

                <h3 style="margin: 2rem 0 1rem; display: flex; align-items: center; gap: 0.5rem;"><span class="material-icons">source</span> Sources ({len(sections)} sections)</h3>
                <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            """

            for i, section in enumerate(sections):
                title_match = (
                    section["identifier"].split(" ")[0]
                    if " " in section["identifier"]
                    else None
                )
                result_html += f"""
                    <div style="padding: 1rem; background: #f7fafc; border-radius: 4px; border-left: 3px solid #667eea;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <strong>{section['identifier']}</strong>: {section['heading']}
                                <span style="color: #666; font-size: 0.85rem; margin-left: 0.5rem;">({section['relevance']:.0%} relevant)</span>
                            </div>
                            {f'<a href="/code/{title_match}" style="color: #0066cc; text-decoration: none; font-size: 0.9rem;">View →</a>' if title_match and title_match.isdigit() else ''}
                        </div>
                    </div>
                """

            result_html += """
                </div>
            </div>
            """

        content = form_html + result_html

    except ImportError as e:
        content = (
            form_html
            + f"""
        <div style="background: #ffe4e1; padding: 1.5rem; border-radius: 8px; margin: 2rem 0;">
            <h3><span class="material-icons" style="vertical-align: middle;">error</span> Missing Library</h3>
            <p>{str(e)}</p>
            <p>Install required packages:</p>
            <pre style="background: #f5f5f5; padding: 1rem; border-radius: 4px; margin: 1rem 0;">pip install openai anthropic</pre>
        </div>
        """
        )
    except Exception as e:
        content = (
            form_html
            + f"""
        <div style="background: #ffe4e1; padding: 1.5rem; border-radius: 8px; margin: 2rem 0;">
            <h3><span class="material-icons" style="vertical-align: middle;">error</span> Error</h3>
            <p>{str(e)}</p>
        </div>
        """
        )

    return render_page("Ask AI", content, "ask")


if __name__ == "__main__":
    print("Starting US Laws Viewer...")
    print("Visit: http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
