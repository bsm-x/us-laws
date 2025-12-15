# US Laws

A comprehensive toolkit for accessing, searching, and analyzing United States federal law. Features semantic search powered by AI embeddings and a web interface for browsing the US Code.

## Features

- **📚 Complete US Code** - All 54 titles of the United States Code in XML format
- **🔍 Semantic Search** - Natural language search across all federal law using OpenAI embeddings
- **🤖 RAG Q&A** - Ask questions about US law and get AI-powered answers with citations
- **🌐 Web Interface** - Browse and search laws through a FastAPI web application
- **📜 Founding Documents** - Read the Declaration of Independence, Constitution, and Bill of Rights (including all Amendments)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your keys:

- `CONGRESS_API_KEY` - Get from [api.congress.gov](https://api.congress.gov/)
- `OPENAI_API_KEY` - Get from [OpenAI](https://platform.openai.com/) (required for semantic search)

### 3. Download the US Code

```bash
python scripts/download/download_full_code.py
```

### 4. Create the Vector Database (Optional - for semantic search)

```bash
python scripts/processing/create_vector_db.py
```

### 5. Run the Web Application

```bash
python -m app.main
```

Visit [http://localhost:8000](http://localhost:8000) to browse the laws.

## Project Structure

```
us-laws/
├── app/                      # Web application
│   ├── main.py              # FastAPI server
│   └── rag.py               # RAG (Retrieval-Augmented Generation)
├── scripts/
│   ├── download/            # Data fetching scripts
│   │   ├── download_full_code.py
│   │   ├── fetch_laws.py
│   │   ├── fetch_policy_areas.py
│   │   └── fetch_uscode_structure.py
│   └── processing/          # Data processing scripts
│       ├── parse_uscode.py
│       ├── create_vector_db.py
│       └── search_code.py
├── data/                    # Downloaded data (git-ignored)
│   ├── founding_documents/
│   ├── uscode/
│   └── vector_db/
└── docs/                    # Documentation
```

## Usage Examples

### Semantic Search (CLI)

```bash
python scripts/processing/search_code.py "copyright protection for software"
```

### Ask a Legal Question (RAG)

```python
from app.rag import ask_question

answer = ask_question("What is the penalty for tax evasion?")
print(answer)
```

### Fetch Public Laws Metadata

```bash
python scripts/download/fetch_laws.py
```

## Data Sources

| Source            | Description               | URL                                           |
| ----------------- | ------------------------- | --------------------------------------------- |
| US Code           | Official US Code in XML   | [uscode.house.gov](https://uscode.house.gov/) |
| Congress.gov      | Public laws and bill data | [api.congress.gov](https://api.congress.gov/) |
| National Archives | Founding documents        | [archives.gov](https://www.archives.gov/)     |

## Tech Stack

- **Backend**: FastAPI, Uvicorn
- **Database**: LanceDB (vector database)
- **Embeddings**: OpenAI text-embedding-3-small
- **LLM**: OpenAI GPT-4o and Anthropic Claude Sonnet 4 (for RAG)
- **Parsing**: Python xml.etree

## API Keys Required

| Key                 | Purpose                      | Required For                             |
| ------------------- | ---------------------------- | ---------------------------------------- |
| `CONGRESS_API_KEY`  | Fetching public law metadata | `fetch_laws.py`, `fetch_policy_areas.py` |
| `OPENAI_API_KEY`    | Embeddings and RAG           | Semantic search, Q&A features            |
| `ANTHROPIC_API_KEY` | Claude LLM (optional)        | Alternative AI for Q&A                   |

## Documentation

- [OpenAI Setup Guide](docs/OPENAI_SETUP.md) - Configure OpenAI API
- [Vector Database Guide](docs/VECTOR_DB_README.md) - Understanding the vector DB
- [RAG Guide](docs/RAG_GUIDE.md) - How the Q&A system works
- [File Formats](docs/FILE_FORMATS.md) - US Code XML format details

## License

This project provides access to public domain US federal law. The code is provided as-is for educational and research purposes.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
