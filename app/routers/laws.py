"""
Public Laws router
"""

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.templates import render_page
from app.data_loaders import load_laws

router = APIRouter(tags=["laws"])


@router.get("/laws", response_class=HTMLResponse)
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
