"""
HTML templates and rendering utilities
Centralizes all HTML/CSS for the application
Dark mode with sidebar layout
"""


def render_page(title: str, content: str, nav_active: str = "") -> str:
    """Render a page with the common layout - dark mode with sidebar"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - US Laws AI</title>
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.6;
            display: flex;
            min-height: 100vh;
        }}

        /* Sidebar */
        .sidebar {{
            width: 260px;
            background: #161b22;
            border-right: 1px solid #30363d;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }}
        .sidebar .logo {{
            font-weight: bold;
            font-size: 1.3rem;
            color: #58a6ff;
            margin-bottom: 2rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .sidebar nav {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}
        .sidebar nav a {{
            color: #c9d1d9;
            text-decoration: none;
            padding: 0.75rem 1rem;
            border-radius: 6px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        .sidebar nav a:hover {{
            background: #21262d;
            color: #58a6ff;
        }}
        .sidebar nav a.active {{
            background: #1f6feb;
            color: #fff;
        }}
        .sidebar .nav-section {{
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid #30363d;
        }}
        .sidebar .nav-section-title {{
            font-size: 0.75rem;
            text-transform: uppercase;
            color: #8b949e;
            margin-bottom: 0.75rem;
            padding-left: 1rem;
        }}

        /* Main content */
        .main-content {{
            flex: 1;
            margin-left: 260px;
            padding: 2rem 3rem;
            min-height: 100vh;
        }}

        h1 {{
            margin-bottom: 1rem;
            color: #f0f6fc;
            font-size: 1.75rem;
        }}
        h2 {{
            margin: 1.5rem 0 1rem;
            color: #c9d1d9;
            font-size: 1.25rem;
        }}
        h3 {{
            color: #c9d1d9;
        }}

        a {{
            color: #58a6ff;
        }}
        a:hover {{
            text-decoration: underline;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat-card {{
            background: #161b22;
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid #30363d;
            text-align: center;
        }}
        .stat-card .number {{
            font-size: 2.5rem;
            font-weight: bold;
            color: #58a6ff;
        }}
        .stat-card .label {{
            color: #8b949e;
            font-size: 0.9rem;
        }}

        table {{
            width: 100%;
            background: #161b22;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #30363d;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid #30363d;
        }}
        th {{
            background: #21262d;
            font-weight: 600;
            color: #c9d1d9;
            position: sticky;
            top: 0;
        }}
        tr:hover {{
            background: #21262d;
        }}

        .search-box {{
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }}
        .search-box input, .search-box select {{
            padding: 0.75rem 1rem;
            border: 1px solid #30363d;
            border-radius: 6px;
            font-size: 1rem;
            background: #0d1117;
            color: #c9d1d9;
        }}
        .search-box input:focus, .search-box select:focus {{
            outline: none;
            border-color: #58a6ff;
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.3);
        }}
        .search-box input {{
            flex: 1;
            min-width: 200px;
        }}
        .search-box button {{
            padding: 0.75rem 1.5rem;
            background: #238636;
            color: #fff;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 500;
            transition: background 0.2s;
        }}
        .search-box button:hover {{
            background: #2ea043;
        }}

        .pagination {{
            display: flex;
            gap: 0.5rem;
            margin-top: 1rem;
            justify-content: center;
        }}
        .pagination a {{
            padding: 0.5rem 1rem;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 6px;
            text-decoration: none;
            color: #c9d1d9;
        }}
        .pagination a:hover, .pagination a.active {{
            background: #1f6feb;
            color: #fff;
            border-color: #1f6feb;
        }}

        .tag {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            background: #21262d;
            border-radius: 4px;
            font-size: 0.8rem;
            color: #8b949e;
        }}
        .tag.enacted {{
            background: #238636;
            color: #fff;
        }}

        .table-wrapper {{
            overflow-x: auto;
            max-height: 70vh;
            overflow-y: auto;
        }}

        .card {{
            background: #161b22;
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid #30363d;
            margin-bottom: 1rem;
        }}

        .alert {{
            padding: 1rem 1.5rem;
            border-radius: 8px;
            margin: 1rem 0;
        }}
        .alert.warning {{
            background: #3d2f00;
            border: 1px solid #634d00;
            color: #f0c43a;
        }}
        .alert.error {{
            background: #3d1f1f;
            border: 1px solid #6d3030;
            color: #f08080;
        }}
        .alert.info {{
            background: #1a3a5c;
            border: 1px solid #2a5a8c;
            color: #79c0ff;
        }}

        pre, code {{
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 0.2rem 0.4rem;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9rem;
        }}
        pre {{
            padding: 1rem;
            overflow-x: auto;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .sidebar {{
                width: 100%;
                height: auto;
                position: relative;
            }}
            .main-content {{
                margin-left: 0;
            }}
            body {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <aside class="sidebar">
        <div class="logo">
            <span class="material-icons">gavel</span>
            US Laws AI
        </div>
        <nav>
            <a href="/" class="{'active' if nav_active == 'home' else ''}">
                <span class="material-icons">search</span>
                AI Search
            </a>
            <a href="/citations" class="{'active' if nav_active == 'citations' else ''}">
                <span class="material-icons">hub</span>
                Citation Graph
            </a>
            <a href="/code" class="{'active' if nav_active == 'code' else ''}">
                <span class="material-icons">menu_book</span>
                US Code
            </a>
            <a href="/scotus" class="{'active' if nav_active == 'scotus' else ''}">
                <span class="material-icons">account_balance</span>
                Supreme Court
            </a>
            <a href="/founding-docs" class="{'active' if nav_active == 'founding_docs' else ''}">
                <span class="material-icons">history_edu</span>
                Founding Docs
            </a>
        </nav>
    </aside>
    <main class="main-content">
        {content}
    </main>
</body>
</html>
"""
