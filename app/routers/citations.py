"""
Citation Graph API Router
Provides endpoints for exploring the citation graph of US Code sections.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from typing import Optional

from app.citations import (
    citation_db_exists,
    get_related_sections,
    get_citation_stats,
    search_citation_path,
)
from app.templates import render_page

router = APIRouter(prefix="/citations", tags=["citations"])


@router.get("", response_class=HTMLResponse)
async def citation_graph_page():
    """Interactive citation graph explorer page"""
    if not citation_db_exists():
        content = """
        <h1>Citation Graph Not Available</h1>
        <p>The citation database hasn't been built yet.</p>
        <h2>To build it:</h2>
        <pre style="background: #161b22; padding: 1rem; border-radius: 8px; overflow-x: auto;">python scripts/processing/build_citation_graph.py</pre>
        """
        return render_page("Citation Graph", content, "citations")

    stats = get_citation_stats()

    # Format most cited sections
    most_cited_html = ""
    for item in stats.get("most_cited", []):
        title = item["title"].lstrip("0")
        section = item["section"]
        count = item["count"]
        most_cited_html += f"""
        <tr onclick="lookupSection('{title}', '{section}')" style="cursor: pointer;">
            <td><a href="/code/{title}">{title} U.S.C. § {section}</a></td>
            <td style="text-align: right;">{count:,}</td>
        </tr>"""

    # Format most citing sections
    most_citing_html = ""
    for item in stats.get("most_citing", []):
        if not item["section"]:  # Skip empty sections
            continue
        title = item["title"].lstrip("0")
        section = item["section"]
        count = item["count"]
        most_citing_html += f"""
        <tr onclick="lookupSection('{title}', '{section}')" style="cursor: pointer;">
            <td><a href="/code/{title}">{title} U.S.C. § {section}</a></td>
            <td style="text-align: right;">{count:,}</td>
        </tr>"""

    content = f"""
    <style>
        .citation-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .lookup-form {{
            background: #161b22;
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid #30363d;
            margin-bottom: 2rem;
        }}
        .lookup-form input {{
            background: #0d1117;
            border: 1px solid #30363d;
            color: #c9d1d9;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            margin-right: 0.5rem;
            width: 100px;
        }}
        .lookup-form button {{
            background: #238636;
            color: white;
            border: none;
            padding: 0.5rem 1.5rem;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
        }}
        .lookup-form button:hover {{
            background: #2ea043;
        }}
        #results {{
            display: none;
            background: #161b22;
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid #30363d;
            margin-bottom: 2rem;
        }}
        .results-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }}
        .results-column h3 {{
            color: #58a6ff;
            margin-bottom: 1rem;
            font-size: 1rem;
        }}
        .ref-link {{
            display: inline-block;
            margin: 0.25rem 0.5rem 0.25rem 0;
            padding: 0.4rem 0.75rem;
            background: #21262d;
            border-radius: 4px;
            font-size: 0.9rem;
            text-decoration: none;
            color: #c9d1d9;
            transition: background 0.2s;
        }}
        .ref-link:hover {{
            background: #30363d;
            color: #58a6ff;
        }}
        .tables-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }}
        @media (max-width: 900px) {{
            .tables-grid, .results-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        table tr:hover {{
            background: #21262d;
        }}
    </style>

    <h1><span class="material-icons" style="vertical-align: middle; margin-right: 0.5rem;">hub</span>Citation Graph</h1>
    <p style="color: #8b949e; margin-bottom: 1.5rem;">Explore how sections of the US Code reference each other.</p>

    <div class="citation-stats">
        <div class="stat-card">
            <div class="number">{stats['total_citations']:,}</div>
            <div class="label">Total Citations</div>
        </div>
        <div class="stat-card">
            <div class="number">{stats['citing_sections']:,}</div>
            <div class="label">Sections That Cite</div>
        </div>
        <div class="stat-card">
            <div class="number">{stats['cited_sections']:,}</div>
            <div class="label">Sections Cited</div>
        </div>
    </div>

    <div class="lookup-form">
        <h2 style="margin-bottom: 1rem; font-size: 1.1rem;">Look Up Section</h2>
        <form onsubmit="lookupSection(); return false;" style="display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
            <input type="text" id="lookup-title" placeholder="Title" required>
            <span style="color: #8b949e;">U.S.C. §</span>
            <input type="text" id="lookup-section" placeholder="Section" required>
            <button type="submit">Find Related</button>
        </form>
    </div>

    <div id="results">
        <h2 id="results-title" style="margin-bottom: 1rem; color: #f0f6fc;"></h2>
        <div class="results-grid">
            <div class="results-column">
                <h3><span class="material-icons" style="vertical-align: middle; font-size: 1rem; margin-right: 0.25rem;">arrow_back</span>Referenced By</h3>
                <div id="cited-by"></div>
            </div>
            <div class="results-column">
                <h3><span class="material-icons" style="vertical-align: middle; font-size: 1rem; margin-right: 0.25rem;">arrow_forward</span>References</h3>
                <div id="cites"></div>
            </div>
        </div>
    </div>

    <div class="tables-grid">
        <div>
            <h2 style="margin-bottom: 1rem;">Most Cited Sections</h2>
            <table>
                <thead>
                    <tr>
                        <th>Section</th>
                        <th style="text-align: right;">Citations</th>
                    </tr>
                </thead>
                <tbody>
                    {most_cited_html}
                </tbody>
            </table>
        </div>
        <div>
            <h2 style="margin-bottom: 1rem;">Sections With Most References</h2>
            <table>
                <thead>
                    <tr>
                        <th>Section</th>
                        <th style="text-align: right;">References</th>
                    </tr>
                </thead>
                <tbody>
                    {most_citing_html}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function lookupSection(title, section) {{
            title = title || document.getElementById('lookup-title').value;
            section = section || document.getElementById('lookup-section').value;

            if (!title || !section) return;

            document.getElementById('lookup-title').value = title;
            document.getElementById('lookup-section').value = section;

            try {{
                const response = await fetch(`/citations/related/${{title}}/${{section}}?limit=20`);
                const data = await response.json();

                if (response.ok) {{
                    document.getElementById('results').style.display = 'block';
                    document.getElementById('results-title').textContent = `${{title}} U.S.C. § ${{section}}`;

                    const citedByDiv = document.getElementById('cited-by');
                    const citesDiv = document.getElementById('cites');

                    if (data.related.cited_by && data.related.cited_by.length > 0) {{
                        citedByDiv.innerHTML = data.related.cited_by.map(ref =>
                            `<a href="/code/${{parseInt(ref.title)}}" class="ref-link" onclick="event.stopPropagation(); lookupSection('${{ref.title.replace(/^0+/, '')}}', '${{ref.section}}')">${{ref.title.replace(/^0+/, '')}} U.S.C. § ${{ref.section}}</a>`
                        ).join('') + `<p style="color: #8b949e; margin-top: 0.5rem; font-size: 0.85rem;">Total: ${{data.related.total_cited_by}}</p>`;
                    }} else {{
                        citedByDiv.innerHTML = '<p style="color: #8b949e;">No sections reference this one.</p>';
                    }}

                    if (data.related.cites && data.related.cites.length > 0) {{
                        citesDiv.innerHTML = data.related.cites.map(ref =>
                            `<a href="/code/${{parseInt(ref.title)}}" class="ref-link" onclick="event.stopPropagation(); lookupSection('${{ref.title.replace(/^0+/, '')}}', '${{ref.section}}')">${{ref.title.replace(/^0+/, '')}} U.S.C. § ${{ref.section}}</a>`
                        ).join('') + `<p style="color: #8b949e; margin-top: 0.5rem; font-size: 0.85rem;">Total: ${{data.related.total_cites}}</p>`;
                    }} else {{
                        citesDiv.innerHTML = '<p style="color: #8b949e;">This section doesn\\'t reference others.</p>';
                    }}

                    document.getElementById('results').scrollIntoView({{ behavior: 'smooth' }});
                }} else {{
                    alert(data.detail || 'Error looking up section');
                }}
            }} catch (error) {{
                console.error('Error:', error);
                alert('Error connecting to the server');
            }}
        }}
    </script>
    """

    return render_page("Citation Graph", content, "citations")


@router.get("/status")
async def get_citation_status():
    """Check if the citation database is available"""
    return {
        "available": citation_db_exists(),
        "message": (
            "Citation graph is ready"
            if citation_db_exists()
            else "Citation database not found. Run 'python scripts/processing/build_citation_graph.py' to create it."
        ),
    }


@router.get("/stats")
async def get_stats():
    """Get statistics about the citation graph"""
    if not citation_db_exists():
        raise HTTPException(
            status_code=503,
            detail="Citation database not found. Run build_citation_graph.py first.",
        )
    return get_citation_stats()


@router.get("/related/{title}/{section}")
async def get_related(
    title: str, section: str, limit: int = Query(default=10, ge=1, le=50)
):
    """
    Get sections related to a given section by citation.

    - **title**: The title number (e.g., "17" for Title 17)
    - **section**: The section number (e.g., "101")
    - **limit**: Maximum number of results per direction (default 10)

    Returns both sections that cite this section and sections this section cites.
    """
    if not citation_db_exists():
        raise HTTPException(
            status_code=503,
            detail="Citation database not found. Run build_citation_graph.py first.",
        )

    identifier = f"/us/usc/t{title}/s{section}"
    related = get_related_sections(identifier, limit)

    return {
        "section": {"title": title, "section": section, "identifier": identifier},
        "related": related,
    }


@router.get("/path")
async def find_citation_path(
    source_title: str = Query(..., description="Source title number"),
    source_section: str = Query(..., description="Source section number"),
    target_title: str = Query(..., description="Target title number"),
    target_section: str = Query(..., description="Target section number"),
    max_depth: int = Query(default=3, ge=1, le=5),
):
    """
    Find citation paths between two sections.

    This performs a breadth-first search to find how two sections are connected
    through citations.
    """
    if not citation_db_exists():
        raise HTTPException(
            status_code=503,
            detail="Citation database not found. Run build_citation_graph.py first.",
        )

    source = f"/us/usc/t{source_title}/s{source_section}"
    target = f"/us/usc/t{target_title}/s{target_section}"

    paths = search_citation_path(source, target, max_depth)

    return {
        "source": {
            "title": source_title,
            "section": source_section,
            "identifier": source,
        },
        "target": {
            "title": target_title,
            "section": target_section,
            "identifier": target,
        },
        "paths_found": len(paths),
        "paths": paths,
    }
