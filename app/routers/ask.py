"""
Ask AI (RAG) router - Home page with streaming support
"""

import html
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
import threading

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from app.templates import render_page
from app.config import get_settings

router = APIRouter(tags=["ask"])
settings = get_settings()

VECTOR_DB_DIR = settings.vector_db_dir

# Thread pool for running sync generators
executor = ThreadPoolExecutor(max_workers=4)


@router.get("/api/stream")
async def stream_answer(q: str = Query(...), provider: str = Query("openai")):
    """Stream AI answer using Server-Sent Events"""
    from app.rag import (
        get_relevant_sections,
        stream_with_openai,
        stream_with_anthropic,
    )

    async def event_generator():
        try:
            # First, retrieve sections (run in thread pool)
            loop = asyncio.get_event_loop()
            uscode_sections = await loop.run_in_executor(
                executor,
                lambda: get_relevant_sections(q, n_results=6),
            )

            # Send sections metadata first (include text for citation popups)
            uscode_data = [
                {
                    "identifier": s.identifier,
                    "heading": s.heading,
                    "relevance": s.relevance,
                    "text": s.text[:1500],  # Include text for citation popups
                }
                for s in uscode_sections
            ]

            yield f"data: {json.dumps({'type': 'uscode_sections', 'content': uscode_data})}\n\n"

            if not uscode_sections:
                yield f"data: {json.dumps({'type': 'error', 'content': 'No relevant US Code sections found.'})}\n\n"
                return

            # Stream the answer
            model_name = "Claude Sonnet 4" if provider == "anthropic" else "GPT-4o"
            yield f"data: {json.dumps({'type': 'model', 'content': model_name})}\n\n"

            # Use a queue to pass chunks from sync generator to async
            chunk_queue: Queue = Queue()
            done_event = threading.Event()
            error_holder = [None]

            def run_stream():
                try:
                    if provider == "anthropic":
                        stream = stream_with_anthropic(q, uscode_sections)
                    else:
                        stream = stream_with_openai(q, uscode_sections)
                    for chunk in stream:
                        chunk_queue.put(chunk)
                except Exception as e:
                    error_holder[0] = e
                finally:
                    done_event.set()

            # Start streaming in background thread
            executor.submit(run_stream)

            # Yield chunks as they come in
            while not done_event.is_set() or not chunk_queue.empty():
                try:
                    chunk = chunk_queue.get(timeout=0.05)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                except Empty:
                    await asyncio.sleep(0.01)

            if error_holder[0]:
                yield f"data: {json.dumps({'type': 'error', 'content': str(error_holder[0])})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/", response_class=HTMLResponse)
async def ask_ai(q: str = Query(""), provider: str = Query("anthropic")):
    """AI Search: Ask questions and get AI-generated answers with streaming"""

    # Check if vector DB exists
    if VECTOR_DB_DIR is None or not VECTOR_DB_DIR.exists():
        content = """
        <h1><span class="material-icons" style="vertical-align: middle;">search</span> Search the US Code</h1>
        <div class="alert warning">
            <h3><span class="material-icons" style="vertical-align: middle;">warning</span> Vector Database Required</h3>
            <p>To use AI Search, create the vector database first:</p>
            <pre>python scripts/processing/create_vector_db.py</pre>
        </div>
        """
        return render_page("AI Search", content, "home")

    # Form HTML with streaming JavaScript
    q_safe = html.escape(q or "", quote=True)
    form_html = f"""
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
        <h1 style="margin: 0; display: flex; align-items: center; gap: 0.5rem;">
            <span class="material-icons" style="font-size: 2rem;">search</span>
            Search the US Code
        </h1>
    </div>

    <p style="color: #8b949e; margin-bottom: 2rem;">Ask natural language questions and get AI-generated answers based on actual US Code sections.</p>

    <form id="askForm" class="search-box" style="margin: 2rem 0;">
        <input type="text" id="questionInput" name="q" placeholder="e.g., 'How long does copyright protection last?'" value="{q_safe}" style="flex: 1;" autofocus>
        <select id="providerSelect" name="provider">
            <option value="anthropic" {"selected" if provider == "anthropic" else ""}>Claude</option>
            <option value="openai" {"selected" if provider == "openai" else ""}>GPT-4</option>
        </select>
        <button type="submit" id="askButton">Ask</button>
    </form>

    <div id="resultContainer"></div>

    <script src="https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js"></script>

    <script>
    const form = document.getElementById('askForm');
    const resultContainer = document.getElementById('resultContainer');
    const askButton = document.getElementById('askButton');

    function escapeHtml(value) {{
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }}

    // Check if there's a query on page load
    const urlParams = new URLSearchParams(window.location.search);
    const initialQuery = urlParams.get('q');
    if (initialQuery) {{
        streamAnswer(initialQuery, urlParams.get('provider') || 'anthropic');
    }}

    form.addEventListener('submit', async (e) => {{
        e.preventDefault();
        const question = document.getElementById('questionInput').value.trim();
        const provider = document.getElementById('providerSelect').value;

        if (!question) return;

        // Update URL without reload
        const newUrl = `?q=${{encodeURIComponent(question)}}&provider=${{provider}}`;
        history.pushState(null, '', newUrl);

        streamAnswer(question, provider);
    }});

    async function streamAnswer(question, provider) {{
        askButton.disabled = true;
        askButton.innerHTML = '<span class="material-icons" style="animation: spin 1s linear infinite;">refresh</span>';

        resultContainer.innerHTML = `
            <div class="card" style="margin-top: 2rem;">
                <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                    <h2 style="margin: 0;">Answer</h2>
                    <span id="modelBadge" style="background: #1f6feb; color: #fff; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: bold;">
                        Loading...
                    </span>
                </div>
                <div id="answerContent" style="line-height: 1.8; padding: 1rem; background: #21262d; border-radius: 6px; min-height: 100px;">
                    <span style="color: #8b949e;">Searching relevant sections...</span>
                </div>

                <div id="sourcesGrid" style="display: none; margin-top: 2rem;">
                    <div class="sources-grid">
                        <div>
                            <h3 style="margin: 0 0 1rem; display: flex; align-items: center; gap: 0.5rem; color: #f0f6fc;">
                                <span class="material-icons" style="color: #58a6ff;">source</span>
                                <span id="sourcesTitle">Sources</span>
                            </h3>
                            <div id="sourcesList"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        try {{
            const response = await fetch(`/api/stream?q=${{encodeURIComponent(question)}}&provider=${{provider}}`);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            let answerText = '';
            const answerContent = document.getElementById('answerContent');

            while (true) {{
                const {{ done, value }} = await reader.read();
                if (done) break;

                const text = decoder.decode(value);
                const lines = text.split('\\n');

                for (const line of lines) {{
                    if (line.startsWith('data: ')) {{
                        try {{
                            const data = JSON.parse(line.slice(6));

                            if (data.type === 'uscode_sections') {{
                                // Store sources for citation popups
                                citationSources = data.content;

                                const sourcesGrid = document.getElementById('sourcesGrid');
                                const sourcesList = document.getElementById('sourcesList');
                                const sourcesTitle = document.getElementById('sourcesTitle');

                                sourcesGrid.style.display = 'block';
                                sourcesTitle.textContent = `US Code Sources (${{data.content.length}} sections)`;

                                sourcesList.innerHTML = data.content.map((s, index) => {{
                                    const sourceNum = index + 1;  // For citation markers [1], [2], etc.
                                    // Parse identifier like "/us/usc/t29/s206" to get title and section
                                    const identMatch = s.identifier.match(/\\/us\\/usc\\/t(\\d+)\\/s(.+)$/);
                                    // Also match "Title 42 “SEC. 221." -> Title 42, Section 221
                                    const titleMatch = s.identifier.match(/Title\\s+(\\d+).*SEC\\.\\s*(\\d+)/i);

                                    let uscLink = '';
                                    let displayName = s.identifier;

                                    if (identMatch) {{
                                        const titleNum = identMatch[1];
                                        const sectionNum = identMatch[2];
                                        uscLink = `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title${{titleNum}}-section${{sectionNum}}&edition=prelim`;
                                        displayName = `USC Title ${{titleNum}} Section ${{sectionNum}}`;
                                    }} else if (titleMatch) {{
                                        const titleNum = titleMatch[1];
                                        const sectionNum = titleMatch[2];
                                        uscLink = `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title${{titleNum}}-section${{sectionNum}}&edition=prelim`;
                                        displayName = `USC Title ${{titleNum}} Section ${{sectionNum}}`;
                                    }} else {{
                                        // Check if it's a founding document
                                        // Simple heuristic: if it's not a path-like string, assume it's a doc title
                                        if (!s.identifier.includes('/')) {{
                                            // Convert "Northwest Ordinance - Article 6" to "northwest_ordinance"
                                            const docName = s.identifier.split(' - ')[0].toLowerCase().replace(/ /g, '_');
                                            uscLink = `/founding-docs/${{docName}}`;
                                            displayName = s.identifier;
                                        }}
                                    }}

                                    // Calculate relevance bar width and color
                                    const relevancePercent = Math.round(s.relevance * 100);
                                    const relevanceColor = relevancePercent >= 70 ? '#238636' : relevancePercent >= 40 ? '#f0883e' : '#8b949e';

                                    return `
                                        <div class="source-card" onclick="showCitation(${{sourceNum}})" style="cursor: pointer;">
                                            <div class="source-header">
                                                <div class="source-title-section">
                                                    <span class="source-number-badge" title="Click to view source text">[<span>${{sourceNum}}</span>]</span>
                                                    ${{uscLink
                                                        ? `<a href="${{uscLink}}" target="_blank" rel="noopener noreferrer" class="source-link" onclick="event.stopPropagation();">
                                                               <span class="material-icons" style="font-size: 1rem; vertical-align: middle;">open_in_new</span>
                                                               ${{displayName}}
                                                           </a>`
                                                        : `<span class="source-identifier">${{displayName}}</span>`
                                                    }}
                                                </div>
                                                <div class="relevance-badge" style="background: ${{relevanceColor}}20; color: ${{relevanceColor}}; border: 1px solid ${{relevanceColor}}40;">
                                                    ${{relevancePercent}}% match
                                                </div>
                                            </div>
                                            <div class="source-heading">${{escapeHtml(s.heading)}}</div>
                                            <div class="relevance-bar-container">
                                                <div class="relevance-bar" style="width: ${{relevancePercent}}%; background: ${{relevanceColor}};"></div>
                                            </div>
                                        </div>
                                    `;
                                }}).join('');

                                answerContent.innerHTML = '<span style="color: #8b949e;">Generating answer...</span>';
                            }}


                            if (data.type === 'model') {{
                                document.getElementById('modelBadge').textContent = data.content;
                            }}

                            if (data.type === 'chunk') {{
                                if (answerText === '') {{
                                    answerContent.innerHTML = '';
                                }}
                                answerText += data.content;
                                // Simple markdown-like rendering
                                answerContent.innerHTML = formatMarkdown(answerText);
                            }}

                            if (data.type === 'error') {{
                                answerContent.innerHTML = `<span style="color: #f08080;">${{data.content}}</span>`;
                            }}
                        }} catch (e) {{
                            // Ignore parse errors for incomplete chunks
                        }}
                    }}
                }}
            }}
        }} catch (error) {{
            resultContainer.innerHTML = `
                <div class="alert error" style="margin: 2rem 0;">
                    <h3><span class="material-icons" style="vertical-align: middle;">error</span> Error</h3>
                    <p>${{error.message}}</p>
                </div>
            `;
        }}

        askButton.disabled = false;
        askButton.textContent = 'Ask';
    }}

    function formatMarkdown(text) {{
        // Use marked library for proper markdown rendering
        try {{
            if (typeof marked !== 'undefined' && marked && typeof marked.parse === 'function') {{
                marked.setOptions({{ gfm: true, breaks: true }});
                let html = marked.parse(text);
                // Convert citation markers [1], [2], etc. to clickable elements
                html = addCitationLinks(html);
                return html;
            }}
            throw new Error('marked not available');
        }} catch (e) {{
            // Fallback to basic formatting
            let html = text
                .replace(/\\n\\n/g, '</p><p>')
                .replace(/\\n/g, '<br>')
                .replace(/^/, '<p>')
                .replace(/$/, '</p>');
            // Convert citation markers
            html = addCitationLinks(html);
            return html;
        }}
    }}

    function addCitationLinks(html) {{
        // Convert [1], [2], etc. to clickable citation markers
        return html.replace(/\\[(\\d+)\\]/g, function(match, num) {{
            return '<span class="citation-marker" data-citation="' + num + '" onclick="showCitation(' + num + ')">[<span>' + num + '</span>]</span>';
        }});
    }}

    // Store sources globally for citation popups
    let citationSources = [];

    function showCitation(num) {{
        const source = citationSources[num - 1];
        if (!source) return;

        // Remove any existing popup
        const existing = document.querySelector('.citation-popup');
        if (existing) existing.remove();

        // Parse identifier to get title and section for display and link
        let displayTitle = source.identifier;
        let uscLink = '';
        const identMatch = source.identifier.match(/\\/us\\/usc\\/t(\\d+)\\/s(.+)$/);
        if (identMatch) {{
            const titleNum = identMatch[1];
            const sectionNum = identMatch[2];
            displayTitle = 'Title ' + titleNum + ' Section ' + sectionNum;
            uscLink = 'https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title' + titleNum + '-section' + sectionNum + '&edition=prelim';
        }}

        // Create popup
        const popup = document.createElement('div');
        popup.className = 'citation-popup';
        const headerContent = uscLink
            ? '<a href="' + uscLink + '" target="_blank" rel="noopener noreferrer" style="color: #58a6ff; text-decoration: none;">[' + num + '] ' + escapeHtml(displayTitle) + ' <span class="material-icons" style="font-size: 0.9rem; vertical-align: middle;">open_in_new</span></a>'
            : '<span>[' + num + '] ' + escapeHtml(displayTitle) + '</span>';
        popup.innerHTML = `
            <div class=\"citation-popup-header\">
                <strong>${{headerContent}}</strong>
                <button onclick=\"this.parentElement.parentElement.remove()\" class=\"citation-close\">&times;</button>
            </div>
            <div class=\"citation-popup-title\">${{escapeHtml(source.heading)}}</div>
            <div class=\"citation-popup-text\">${{escapeHtml(source.text.substring(0, 800))}}</div>
            <div class=\"citation-popup-relevance\">
                <span style=\"color: #8b949e;\">Relevance:</span>
                <span style=\"color: #58a6ff; font-weight: bold;\">${{Math.round(source.relevance * 100)}}%</span>
            </div>
        `;

        document.body.appendChild(popup);

        // Position near center of screen
        popup.style.top = '50%';
        popup.style.left = '50%';
        popup.style.transform = 'translate(-50%, -50%)';

        // Close on outside click
        setTimeout(() => {{
            document.addEventListener('click', function closePopup(e) {{
                if (!popup.contains(e.target) && !e.target.classList.contains('citation-marker')) {{
                    popup.remove();
                    document.removeEventListener('click', closePopup);
                }}
            }});
        }}, 100);
    }}
    </script>

    <style>
    @keyframes spin {{
        from {{ transform: rotate(0deg); }}
        to {{ transform: rotate(360deg); }}
    }}

    /* Citation Markers */
    .citation-marker {{
        display: inline;
        color: #58a6ff;
        cursor: pointer;
        font-weight: 600;
        background: rgba(88, 166, 255, 0.15);
        padding: 0 0.2rem;
        border-radius: 3px;
        transition: all 0.2s;
        font-size: 0.85em;
        vertical-align: super;
    }}
    .citation-marker:hover {{
        background: rgba(88, 166, 255, 0.3);
        color: #79c0ff;
    }}
    .citation-marker span {{
        text-decoration: underline;
    }}

    /* Citation Popup */
    .citation-popup {{
        position: fixed;
        z-index: 10000;
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
        max-width: 550px;
        width: 90%;
        max-height: 80vh;
        overflow: hidden;
        animation: popupFadeIn 0.2s ease;
    }}
    @keyframes popupFadeIn {{
        from {{ opacity: 0; transform: translate(-50%, -50%) scale(0.95); }}
        to {{ opacity: 1; transform: translate(-50%, -50%) scale(1); }}
    }}
    .citation-popup-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 1.25rem;
        background: #21262d;
        border-bottom: 1px solid #30363d;
        color: #58a6ff;
        font-size: 0.95rem;
    }}
    .citation-close {{
        background: none;
        border: none;
        color: #8b949e;
        font-size: 1.5rem;
        cursor: pointer;
        padding: 0 0.25rem;
        line-height: 1;
    }}
    .citation-close:hover {{
        color: #f08080;
    }}
    .citation-popup-title {{
        padding: 0.75rem 1.25rem;
        font-weight: 600;
        color: #f0f6fc;
        background: #1c2128;
    }}
    .citation-popup-text {{
        padding: 1rem 1.25rem;
        color: #c9d1d9;
        font-size: 0.9rem;
        line-height: 1.7;
        max-height: 300px;
        overflow-y: auto;
        white-space: pre-wrap;
    }}
    .citation-popup-relevance {{
        padding: 0.75rem 1.25rem;
        background: #21262d;
        border-top: 1px solid #30363d;
        font-size: 0.85rem;
    }}

    #answerContent h1, #answerContent h2, #answerContent h3 {{
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }}
    #answerContent ul, #answerContent ol {{
        padding-left: 1.5rem;
        margin: 0.5rem 0;
    }}
    #answerContent li {{
        margin: 0.25rem 0;
    }}
    #answerContent p {{
        margin: 0.5rem 0;
    }}
    #answerContent code {{
        background: #161b22;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
        font-size: 0.9rem;
    }}
    #answerContent pre {{
        background: #161b22;
        padding: 1rem;
        border-radius: 6px;
        overflow-x: auto;
    }}
    #answerContent blockquote {{
        border-left: 3px solid #58a6ff;
        padding-left: 1rem;
        margin: 0.5rem 0;
        color: #8b949e;
    }}

    /* Source Cards Styling */
    .source-card {{
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        transition: all 0.2s ease;
    }}
    .source-card:hover {{
        border-color: #58a6ff;
        box-shadow: 0 4px 12px rgba(88, 166, 255, 0.15);
        transform: translateY(-2px);
    }}
    .source-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
        flex-wrap: wrap;
        gap: 0.5rem;
    }}
    .source-title-section {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }}
    .source-number-badge {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(88, 166, 255, 0.2);
        color: #58a6ff;
        font-weight: 700;
        font-size: 0.85rem;
        padding: 0.15rem 0.4rem;
        border-radius: 4px;
        border: 1px solid rgba(88, 166, 255, 0.4);
        transition: all 0.2s;
    }}
    .source-number-badge span {{
        text-decoration: underline;
    }}
    .source-card:hover .source-number-badge {{
        background: rgba(88, 166, 255, 0.35);
        color: #79c0ff;
    }}
    .source-link {{
        color: #58a6ff;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.95rem;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        transition: color 0.2s;
    }}
    .source-link:hover {{
        color: #79c0ff;
        text-decoration: underline;
    }}
    .source-identifier {{
        color: #f0f6fc;
        font-weight: 600;
        font-size: 0.95rem;
    }}
    .relevance-badge {{
        padding: 0.25rem 0.6rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
    }}
    .source-heading {{
        color: #c9d1d9;
        font-size: 0.9rem;
        margin-bottom: 0.75rem;
        line-height: 1.4;
    }}
    .relevance-bar-container {{
        height: 4px;
        background: #21262d;
        border-radius: 2px;
        overflow: hidden;
    }}
    .relevance-bar {{
        height: 100%;
        border-radius: 2px;
        transition: width 0.3s ease;
    }}
    #sourcesList {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
    }}

    .sources-grid {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 1rem;
        align-items: start;
    }}
    @media (max-width: 1000px) {{
        #sourcesList {{
            grid-template-columns: 1fr;
        }}
    }}
    #foundingList {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 1rem;
    }}
    </style>
    """

    if not q:
        # Show examples when no query
        examples_html = """
        <div class="card">
            <h2>Example Questions</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-top: 1rem;">
                <div style="padding: 1rem; background: #21262d; border-radius: 6px;">
                    <strong style="color: #58a6ff;"><span class="material-icons" style="vertical-align: middle; font-size: 1.2rem;">book</span> Copyright & IP</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem; color: #8b949e;">
                        <li><a href="/?q=How+long+does+copyright+protection+last">How long does copyright protection last?</a></li>
                        <li><a href="/?q=What+is+fair+use+under+copyright+law">What is fair use under copyright law?</a></li>
                        <li><a href="/?q=How+do+I+register+a+patent">How do I register a patent?</a></li>
                    </ul>
                </div>
                <div style="padding: 1rem; background: #21262d; border-radius: 6px;">
                    <strong style="color: #58a6ff;"><span class="material-icons" style="vertical-align: middle; font-size: 1.2rem;">business</span> Business & Tax</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem; color: #8b949e;">
                        <li><a href="/?q=Can+I+deduct+home+office+expenses">Can I deduct home office expenses?</a></li>
                        <li><a href="/?q=What+is+the+corporate+tax+rate">What is the corporate tax rate?</a></li>
                        <li><a href="/?q=How+are+capital+gains+taxed">How are capital gains taxed?</a></li>
                    </ul>
                </div>
                <div style="padding: 1rem; background: #21262d; border-radius: 6px;">
                    <strong style="color: #58a6ff;"><span class="material-icons" style="vertical-align: middle; font-size: 1.2rem;">gavel</span> Criminal Law</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem; color: #8b949e;">
                        <li><a href="/?q=What+are+penalties+for+wire+fraud">What are penalties for wire fraud?</a></li>
                        <li><a href="/?q=What+constitutes+insider+trading">What constitutes insider trading?</a></li>
                        <li><a href="/?q=What+are+federal+drug+laws">What are federal drug laws?</a></li>
                    </ul>
                </div>
                <div style="padding: 1rem; background: #21262d; border-radius: 6px;">
                    <strong style="color: #58a6ff;"><span class="material-icons" style="vertical-align: middle; font-size: 1.2rem;">people</span> Employment</strong>
                    <ul style="margin-top: 0.5rem; padding-left: 1.5rem; color: #8b949e;">
                        <li><a href="/?q=What+is+the+federal+minimum+wage">What is the federal minimum wage?</a></li>
                        <li><a href="/?q=What+workplace+discrimination+is+illegal">What workplace discrimination is illegal?</a></li>
                        <li><a href="/?q=What+are+FMLA+leave+requirements">What are FMLA leave requirements?</a></li>
                    </ul>
                </div>
            </div>

        </div>
        """
        content = form_html + examples_html
    else:
        # With a query, just show the form - streaming JS will handle the rest
        content = form_html

    return render_page("AI Search", content, "home")
