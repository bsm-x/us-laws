"""
Supreme Court Opinions router - Browse and search SCOTUS opinions
"""

import html
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.templates import render_page
from app.config import get_settings

router = APIRouter(prefix="/scotus", tags=["scotus"])
settings = get_settings()

# Database path
SCOTUS_DB = settings.data_dir / "scotus" / "scotus_opinions.db"


def get_db_connection():
    """Get SQLite database connection."""
    if not SCOTUS_DB.exists():
        return None
    return sqlite3.connect(SCOTUS_DB)


def get_stats():
    """Get database statistics."""
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM cases")
    case_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM opinions")
    opinion_count = cursor.fetchone()[0]

    cursor.execute(
        "SELECT MIN(date_filed), MAX(date_filed) FROM cases WHERE date_filed != ''"
    )
    date_range = cursor.fetchone()

    conn.close()

    return {
        "cases": case_count,
        "opinions": opinion_count,
        "oldest": date_range[0] if date_range else None,
        "newest": date_range[1] if date_range else None,
    }


@router.get("/", response_class=HTMLResponse)
async def scotus_home(
    page: int = Query(1, ge=1),
    year: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
):
    """Supreme Court Opinions browser - main page"""

    conn = get_db_connection()
    if not conn:
        content = """
        <h1><span class="material-icons" style="vertical-align: middle;">gavel</span> Supreme Court Opinions</h1>
        <div class="alert warning">
            <h3><span class="material-icons" style="vertical-align: middle;">warning</span> Database Not Found</h3>
            <p>Download Supreme Court opinions first:</p>
            <pre>python scripts/download/download_scotus_opinions.py</pre>
        </div>
        """
        return render_page("Supreme Court", content, "scotus")

    cursor = conn.cursor()

    # Get stats
    stats = get_stats()

    # Build query
    per_page = 25
    offset = (page - 1) * per_page

    where_clauses = []
    params = []

    if year:
        where_clauses.append("strftime('%Y', c.date_filed) = ?")
        params.append(str(year))

    if search:
        where_clauses.append("(c.case_name LIKE ? OR c.case_name_short LIKE ?)")
        search_term = f"%{search}%"
        params.extend([search_term, search_term])

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Count total
    cursor.execute(
        f"""
        SELECT COUNT(DISTINCT c.id)
        FROM cases c
        {where_sql}
    """,
        params,
    )
    total_count = cursor.fetchone()[0]
    total_pages = (total_count + per_page - 1) // per_page

    # Get cases with opinion counts
    cursor.execute(
        f"""
        SELECT
            c.id, c.cluster_id, c.case_name, c.case_name_short,
            c.date_filed, c.citation, c.docket_number,
            COUNT(o.id) as opinion_count
        FROM cases c
        LEFT JOIN opinions o ON c.id = o.case_id
        {where_sql}
        GROUP BY c.id
        ORDER BY c.date_filed DESC
        LIMIT ? OFFSET ?
    """,
        params + [per_page, offset],
    )

    cases = cursor.fetchall()

    # Get available years for filter
    cursor.execute(
        """
        SELECT DISTINCT strftime('%Y', date_filed) as year
        FROM cases
        WHERE date_filed != ''
        ORDER BY year DESC
    """
    )
    years = [r[0] for r in cursor.fetchall() if r[0]]

    conn.close()

    # Build HTML
    search_value = html.escape(search or "", quote=True)

    content = f"""
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
        <h1 style="margin: 0; display: flex; align-items: center; gap: 0.5rem;">
            <span class="material-icons" style="font-size: 2rem;">gavel</span>
            Supreme Court Opinions
        </h1>
    </div>

    <p style="color: #8b949e; margin-bottom: 2rem;">
        Browse {stats['cases']:,} cases and {stats['opinions']:,} opinions from the Supreme Court of the United States.
        {f"Spanning from {stats['oldest'][:4]} to {stats['newest'][:4]}." if stats['oldest'] else ""}
    </p>

    <div class="stats" style="margin-bottom: 2rem;">
        <div class="stat-card">
            <div class="number">{stats['cases']:,}</div>
            <div class="label">Cases</div>
        </div>
        <div class="stat-card">
            <div class="number">{stats['opinions']:,}</div>
            <div class="label">Opinions</div>
        </div>
        <div class="stat-card">
            <div class="number">{stats['oldest'][:4] if stats['oldest'] else 'N/A'}</div>
            <div class="label">Oldest Case</div>
        </div>
        <div class="stat-card">
            <div class="number">{stats['newest'][:4] if stats['newest'] else 'N/A'}</div>
            <div class="label">Newest Case</div>
        </div>
    </div>

    <form class="search-box" method="get" action="/scotus">
        <input type="text" name="search" placeholder="Search cases by name..."
               value="{search_value}" style="flex: 1;">
        <select name="year">
            <option value="">All Years</option>
            {"".join(f'<option value="{y}" {"selected" if str(year) == y else ""}>{y}</option>' for y in years)}
        </select>
        <button type="submit">Search</button>
    </form>

    <div style="margin-bottom: 1rem; color: #8b949e;">
        Showing {offset + 1}-{min(offset + per_page, total_count)} of {total_count:,} cases
        {f" matching '{html.escape(search)}'" if search else ""}
        {f" from {year}" if year else ""}
    </div>

    <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Case</th>
                    <th>Date</th>
                    <th>Citation</th>
                    <th>Opinions</th>
                </tr>
            </thead>
            <tbody>
    """

    for case in cases:
        (
            case_id,
            cluster_id,
            case_name,
            case_name_short,
            date_filed,
            citation,
            docket_number,
            opinion_count,
        ) = case

        display_name = case_name_short or case_name or f"Case #{cluster_id}"
        date_display = date_filed[:10] if date_filed else "Unknown"

        content += f"""
                <tr>
                    <td>
                        <a href="/scotus/case/{cluster_id}" style="color: #58a6ff; text-decoration: none; font-weight: 500;">
                            {html.escape(display_name)}
                        </a>
                        {f'<div style="font-size: 0.85rem; color: #8b949e; margin-top: 0.25rem;">{html.escape(docket_number)}</div>' if docket_number else ''}
                    </td>
                    <td>{date_display}</td>
                    <td><code style="font-size: 0.85rem;">{html.escape(citation or '')}</code></td>
                    <td>{opinion_count}</td>
                </tr>
        """

    content += """
            </tbody>
        </table>
    </div>
    """

    # Pagination
    if total_pages > 1:
        content += '<div class="pagination">'

        # Build base URL with existing params
        base_params = []
        if search:
            base_params.append(f"search={html.escape(search, quote=True)}")
        if year:
            base_params.append(f"year={year}")
        base_url = "/scotus?" + "&".join(base_params) + ("&" if base_params else "")

        if page > 1:
            content += f'<a href="{base_url}page={page-1}">← Previous</a>'

        # Show page numbers
        start_page = max(1, page - 3)
        end_page = min(total_pages, page + 3)

        if start_page > 1:
            content += f'<a href="{base_url}page=1">1</a>'
            if start_page > 2:
                content += '<span style="color: #8b949e; padding: 0.5rem;">...</span>'

        for p in range(start_page, end_page + 1):
            if p == page:
                content += f'<a class="active">{p}</a>'
            else:
                content += f'<a href="{base_url}page={p}">{p}</a>'

        if end_page < total_pages:
            if end_page < total_pages - 1:
                content += '<span style="color: #8b949e; padding: 0.5rem;">...</span>'
            content += f'<a href="{base_url}page={total_pages}">{total_pages}</a>'

        if page < total_pages:
            content += f'<a href="{base_url}page={page+1}">Next →</a>'

        content += "</div>"

    return render_page("Supreme Court Opinions", content, "scotus")


@router.get("/case/{cluster_id}", response_class=HTMLResponse)
async def view_case(cluster_id: int):
    """View a specific Supreme Court case and its opinions."""

    conn = get_db_connection()
    if not conn:
        return render_page("Case Not Found", "<h1>Database not found</h1>", "scotus")

    cursor = conn.cursor()

    # Get case info
    cursor.execute(
        """
        SELECT id, cluster_id, case_name, case_name_short, date_filed,
               citation, docket_number, judges, syllabus, procedural_history, attorneys
        FROM cases
        WHERE cluster_id = ?
    """,
        (cluster_id,),
    )

    case = cursor.fetchone()
    if not case:
        conn.close()
        return render_page(
            "Case Not Found", f"<h1>Case {cluster_id} not found</h1>", "scotus"
        )

    (
        case_id,
        cluster_id,
        case_name,
        case_name_short,
        date_filed,
        citation,
        docket_number,
        judges,
        syllabus,
        procedural_history,
        attorneys,
    ) = case

    # Get opinions
    cursor.execute(
        """
        SELECT opinion_id, type, author, plain_text, word_count
        FROM opinions
        WHERE case_id = ?
        ORDER BY type
    """,
        (case_id,),
    )

    opinions = cursor.fetchall()
    conn.close()

    # Opinion type labels
    type_labels = {
        "010combined": "Opinion of the Court",
        "015unanimous": "Unanimous Opinion",
        "020lead": "Lead Opinion",
        "025plurality": "Plurality Opinion",
        "030concurrence": "Concurring Opinion",
        "035concurrenceinpart": "Concurring in Part",
        "040dissent": "Dissenting Opinion",
        "045dissentinpart": "Dissenting in Part",
        "050addendum": "Addendum",
        "060rehearing": "Rehearing",
        "070onthemerits": "On the Merits",
        "080onremand": "On Remand",
    }

    display_name = case_name_short or case_name or f"Case #{cluster_id}"

    content = f"""
    <div style="margin-bottom: 1rem;">
        <a href="/scotus" style="color: #8b949e; text-decoration: none; display: inline-flex; align-items: center; gap: 0.25rem;">
            <span class="material-icons" style="font-size: 1rem;">arrow_back</span>
            Back to Cases
        </a>
    </div>

    <h1 style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
        <span class="material-icons" style="color: #58a6ff;">gavel</span>
        {html.escape(display_name)}
    </h1>

    <div style="display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 2rem; color: #8b949e;">
        {f'<span><strong>Decided:</strong> {date_filed[:10]}</span>' if date_filed else ''}
        {f'<span><strong>Citation:</strong> <code>{html.escape(citation)}</code></span>' if citation else ''}
        {f'<span><strong>Docket:</strong> {html.escape(docket_number)}</span>' if docket_number else ''}
    </div>
    """

    # Full case name if different
    if case_name and case_name != case_name_short:
        content += f"""
        <div class="card" style="margin-bottom: 1.5rem;">
            <h3 style="margin-top: 0;">Full Case Name</h3>
            <p style="margin: 0; color: #c9d1d9;">{html.escape(case_name)}</p>
        </div>
        """

    # Syllabus
    if syllabus:
        content += f"""
        <div class="card" style="margin-bottom: 1.5rem;">
            <h3 style="margin-top: 0;">Syllabus</h3>
            <p style="margin: 0; color: #c9d1d9; white-space: pre-wrap;">{html.escape(syllabus[:2000])}{'...' if len(syllabus) > 2000 else ''}</p>
        </div>
        """

    # Opinions
    content += f"""
    <h2 style="display: flex; align-items: center; gap: 0.5rem; margin-top: 2rem;">
        <span class="material-icons">description</span>
        Opinions ({len(opinions)})
    </h2>
    """

    for i, (opinion_id, opinion_type, author, text, word_count) in enumerate(opinions):
        type_label = type_labels.get(opinion_type, opinion_type or "Opinion")

        # Determine badge color
        if "dissent" in (opinion_type or "").lower():
            badge_color = "#f08080"
        elif "concur" in (opinion_type or "").lower():
            badge_color = "#f0c43a"
        else:
            badge_color = "#58a6ff"

        content += f"""
        <div class="card" style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0; display: flex; align-items: center; gap: 0.5rem;">
                    <span style="background: {badge_color}20; color: {badge_color}; padding: 0.25rem 0.75rem; border-radius: 4px; font-size: 0.85rem;">
                        {type_label}
                    </span>
                    {f'<span style="color: #c9d1d9; font-weight: normal;">by {html.escape(author)}</span>' if author else ''}
                </h3>
                <span style="color: #8b949e; font-size: 0.85rem;">{word_count:,} words</span>
            </div>
            <details>
                <summary style="cursor: pointer; color: #58a6ff; margin-bottom: 1rem;">Show full opinion text</summary>
                <div style="background: #21262d; padding: 1.5rem; border-radius: 6px; max-height: 500px; overflow-y: auto; white-space: pre-wrap; font-size: 0.9rem; line-height: 1.7;">
{html.escape(text or "No text available")}
                </div>
            </details>
        </div>
        """

    # External link to CourtListener
    content += f"""
    <div style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #30363d;">
        <a href="https://www.courtlistener.com/opinion/{cluster_id}/" target="_blank" rel="noopener noreferrer"
           style="display: inline-flex; align-items: center; gap: 0.5rem; color: #58a6ff;">
            <span class="material-icons">open_in_new</span>
            View on CourtListener
        </a>
    </div>
    """

    return render_page(display_name, content, "scotus")


@router.get("/api/search", response_class=HTMLResponse)
async def search_opinions(q: str = Query(..., min_length=1)):
    """API endpoint to search opinions using vector similarity."""
    # This will be implemented when we integrate with RAG
    pass
