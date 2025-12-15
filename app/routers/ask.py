"""
Ask AI (RAG) router - Home page with streaming support
"""

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
            sections = await loop.run_in_executor(
                executor, lambda: get_relevant_sections(q, n_results=5)
            )

            if not sections:
                yield f"data: {json.dumps({'type': 'error', 'content': 'No relevant sections found.'})}\n\n"
                return

            # Send sections metadata first
            sections_data = [
                {
                    "identifier": s.identifier,
                    "heading": s.heading,
                    "relevance": s.relevance,
                }
                for s in sections
            ]
            yield f"data: {json.dumps({'type': 'sections', 'content': sections_data})}\n\n"

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
                        stream = stream_with_anthropic(q, sections)
                    else:
                        stream = stream_with_openai(q, sections)
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
async def ask_ai(q: str = Query(""), provider: str = Query("openai")):
    """RAG: Ask questions and get AI-generated answers with streaming"""

    # Check if vector DB exists
    if VECTOR_DB_DIR is None or not VECTOR_DB_DIR.exists():
        content = """
        <h1><span class="material-icons" style="vertical-align: middle;">chat</span> Ask AI About US Code</h1>
        <div class="alert warning">
            <h3><span class="material-icons" style="vertical-align: middle;">warning</span> Vector Database Required</h3>
            <p>To use AI Q&A, create the vector database first:</p>
            <pre>python scripts/processing/create_vector_db.py</pre>
        </div>
        """
        return render_page("Ask AI", content, "home")

    # Form HTML with streaming JavaScript
    form_html = f"""
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
        <h1 style="margin: 0; display: flex; align-items: center; gap: 0.5rem;">
            <span class="material-icons" style="font-size: 2rem;">chat</span>
            Ask Questions About US Code
        </h1>
        <span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: bold;">
            RAG Powered
        </span>
    </div>
    <p style="color: #8b949e; margin-bottom: 2rem;">Ask natural language questions and get AI-generated answers based on actual US Code sections.</p>

    <form id="askForm" class="search-box" style="margin: 2rem 0;">
        <input type="text" id="questionInput" name="q" placeholder="e.g., 'How long does copyright protection last?'" value="{q}" style="flex: 1;" autofocus>
        <select id="providerSelect" name="provider">
            <option value="openai" {"selected" if provider == "openai" else ""}>GPT-4</option>
            <option value="anthropic" {"selected" if provider == "anthropic" else ""}>Claude</option>
        </select>
        <button type="submit" id="askButton">Ask</button>
    </form>

    <div id="resultContainer"></div>

    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>
    // Configure marked for safe rendering
    marked.setOptions({{
        breaks: true,
        gfm: true
    }});

    const form = document.getElementById('askForm');
    const resultContainer = document.getElementById('resultContainer');
    const askButton = document.getElementById('askButton');

    // Check if there's a query on page load
    const urlParams = new URLSearchParams(window.location.search);
    const initialQuery = urlParams.get('q');
    if (initialQuery) {{
        streamAnswer(initialQuery, urlParams.get('provider') || 'openai');
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
                <div id="sourcesContainer" style="display: none;">
                    <h3 style="margin: 2rem 0 1rem; display: flex; align-items: center; gap: 0.5rem;">
                        <span class="material-icons">source</span> <span id="sourcesTitle">Sources</span>
                    </h3>
                    <div id="sourcesList" style="display: flex; flex-direction: column; gap: 0.5rem;"></div>
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

                            if (data.type === 'sections') {{
                                const sourcesContainer = document.getElementById('sourcesContainer');
                                const sourcesList = document.getElementById('sourcesList');
                                const sourcesTitle = document.getElementById('sourcesTitle');

                                sourcesContainer.style.display = 'block';
                                sourcesTitle.textContent = `Sources (${{data.content.length}} sections)`;

                                sourcesList.innerHTML = data.content.map(s => {{
                                    const titleNum = s.identifier.split(' ')[0];
                                    const viewLink = /^\\d+$/.test(titleNum)
                                        ? `<a href="/code/${{titleNum}}" style="font-size: 0.9rem;">View →</a>`
                                        : '';
                                    return `
                                        <div style="padding: 1rem; background: #21262d; border-radius: 6px; border-left: 3px solid #58a6ff;">
                                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                                <div>
                                                    <strong style="color: #f0f6fc;">${{s.identifier}}</strong>: ${{s.heading}}
                                                    <span style="color: #8b949e; font-size: 0.85rem; margin-left: 0.5rem;">(${{Math.round(s.relevance * 100)}}% relevant)</span>
                                                </div>
                                                ${{viewLink}}
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
            return marked.parse(text);
        }} catch (e) {{
            // Fallback to basic formatting
            return text
                .replace(/\\n\\n/g, '</p><p>')
                .replace(/\\n/g, '<br>')
                .replace(/^/, '<p>')
                .replace(/$/, '</p>');
        }}
    }}
    </script>

    <style>
    @keyframes spin {{
        from {{ transform: rotate(0deg); }}
        to {{ transform: rotate(360deg); }}
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

            <div class="alert info" style="margin-top: 2rem;">
                <h3 style="margin: 0 0 0.5rem; color: #58a6ff;">How RAG Works</h3>
                <ol style="margin: 0.5rem 0; padding-left: 1.5rem;">
                    <li><strong>Retrieve:</strong> Searches vector database for relevant US Code sections</li>
                    <li><strong>Augment:</strong> Adds those sections as context to your question</li>
                    <li><strong>Generate:</strong> AI generates an answer based only on retrieved sections</li>
                </ol>
                <p style="margin: 0.5rem 0 0; font-size: 0.9rem; color: #8b949e;">
                    Answers are grounded in actual law, with citations to specific sections.
                </p>
            </div>
        </div>
        """
        content = form_html + examples_html
    else:
        # With a query, just show the form - streaming JS will handle the rest
        content = form_html

    return render_page("Ask AI", content, "home")
