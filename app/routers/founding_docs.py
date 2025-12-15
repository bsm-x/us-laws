from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.templates import render_page

router = APIRouter(tags=["founding_docs"])
settings = get_settings()

DOCS_DIR = settings.data_dir / "founding_documents"

DOC_METADATA = {
    "declaration_of_independence": {
        "year": 1776,
        "title": "Declaration of Independence",
    },
    "articles_of_confederation": {"year": 1777, "title": "Articles of Confederation"},
    "northwest_ordinance": {"year": 1787, "title": "Northwest Ordinance"},
    "constitution": {"year": 1787, "title": "Constitution of the United States"},
    "bill_of_rights": {"year": 1791, "title": "Bill of Rights"},
}


def get_doc_info(stem: str) -> dict:
    info = DOC_METADATA.get(stem, {})
    return {
        "title": info.get("title", stem.replace("_", " ").title()),
        "year": info.get("year", 9999),
    }


@router.get("/founding-docs", response_class=HTMLResponse)
async def list_founding_docs():
    """List all founding documents"""
    docs = []
    if DOCS_DIR.exists():
        for f in DOCS_DIR.glob("*.txt"):
            info = get_doc_info(f.stem)
            docs.append({"name": info["title"], "year": info["year"], "slug": f.stem})

    # Sort by year
    docs.sort(key=lambda x: x["year"])

    doc_items = "\n".join(
        f"""<a href="/founding-docs/{d["slug"]}" class="doc-item">
            <div style="flex: 1;">
                <div style="font-weight: 600;">{d["name"]}</div>
                <div style="font-size: 0.85rem; color: #8b949e; margin-top: 0.25rem;">{d["year"] if d["year"] != 9999 else ""}</div>
            </div>
            <span class="material-icons" style="color: #8b949e;">chevron_right</span>
        </a>"""
        for d in docs
    )

    content = f"""
    <style>
        .docs-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1rem;
            margin-top: 2rem;
        }}
        .doc-item {{
            background: #161b22;
            border: 1px solid #30363d;
            color: #c9d1d9;
            text-decoration: none;
            padding: 1.5rem;
            border-radius: 6px;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            gap: 1rem;
            transition: all 0.2s;
        }}
        .doc-item:hover {{
            background: #21262d;
            border-color: #58a6ff;
            color: #58a6ff;
            transform: translateY(-2px);
        }}
    </style>

    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
        <h1 style="margin: 0; display: flex; align-items: center; gap: 0.5rem;">
            <span class="material-icons" style="font-size: 2rem;">history_edu</span>
            Founding Documents
        </h1>
    </div>

    <p style="color: #8b949e; max-width: 800px;">
        Essential historical documents that established the United States government and its fundamental laws.
    </p>

    <div class="docs-grid">
        {doc_items}
    </div>
    """

    return render_page("Founding Documents", content, "founding_docs")


@router.get("/founding-docs/{doc_name}", response_class=HTMLResponse)
async def view_founding_doc(doc_name: str):
    """View a specific founding document"""
    # Security check: ensure no path traversal
    safe_name = Path(doc_name).name
    # Ensure extension is .txt if not provided
    if not safe_name.endswith(".txt"):
        safe_name += ".txt"

    file_path = DOCS_DIR / safe_name

    if not file_path.exists():
        # Try replacing spaces with underscores if it came from a URL
        safe_name = safe_name.replace(" ", "_").lower()
        file_path = DOCS_DIR / safe_name

        if not file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Document not found: {doc_name}"
            )

    content = file_path.read_text(encoding="utf-8")
    info = get_doc_info(Path(safe_name).stem)
    title = info["title"]
    year = info["year"]
    year_badge = (
        f'<span style="background: #30363d; color: #8b949e; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.9rem; vertical-align: middle; margin-left: 1rem;">{year}</span>'
        if year != 9999
        else ""
    )

    html_content = f"""
    <div class="breadcrumbs" style="margin-bottom: 1rem;">
        <a href="/founding-docs" style="color: #58a6ff; text-decoration: none;">Founding Docs</a> &gt; <span style="color: #8b949e;">{title}</span>
    </div>

    <h1 style="border-bottom: 1px solid #30363d; padding-bottom: 0.5rem; margin-bottom: 2rem;">
        {title}
        {year_badge}
    </h1>

    <div class="document-content" style="white-space: pre-wrap; font-family: 'Georgia', serif; font-size: 1.1rem; line-height: 1.8; max-width: 800px; margin: 0 auto; background: #0d1117; padding: 2rem; border: 1px solid #30363d; border-radius: 8px; color: #c9d1d9;">
{content}
    </div>
    """

    return render_page(title, html_content, "founding_docs")
