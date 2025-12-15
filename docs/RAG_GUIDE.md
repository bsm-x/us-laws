# RAG (Retrieval-Augmented Generation) Guide

## What is RAG?

RAG combines:

1. **Retrieval**: Finding relevant US Code sections from vector database
2. **Augmentation**: Adding those sections as context to your question
3. **Generation**: LLM generates answer based only on retrieved sections

## Why RAG?

- ✅ **Accurate**: Answers grounded in actual law, not hallucinations
- ✅ **Cited**: References specific code sections
- ✅ **Up-to-date**: Uses your current US Code data
- ✅ **Verifiable**: Can check sources directly

## Usage

### Web Interface

Visit http://localhost:8000 (AI Search is the home page)

**Features:**

- Natural language questions
- Choose between GPT-4 or Claude
- Real-time streaming responses
- **Inline citations** - AI answers include numbered markers like [1], [2]
- **Citation popups** - Click any [1], [2] marker to see the source text
- **Source cards** - Each source shows relevance score and links to official US Code
- Example questions provided

### Citation Popups

When the AI generates an answer, it includes citation markers like [1], [2], etc. These are clickable:

1. **Click a citation marker** in the answer text (e.g., "[1]")
2. **Popup appears** showing:
   - Source number and title (e.g., "[1] Title 29 Section 206")
   - Clickable link to official US Code website
   - Section heading
   - First 800 characters of the source text
   - Relevance score
3. **Click outside** or the × button to close

The source cards below the answer also show [1], [2] badges - click any card to see the same popup.

### Command Line

```bash
# Using OpenAI GPT-4 (default)
python -m app.rag "How long does copyright protection last?"

# Using Anthropic Claude
python -m app.rag --claude "What are penalties for wire fraud?"

# Interactive mode
python -m app.rag
```

## Example Questions

### Copyright & IP

- "How long does copyright protection last?"
- "What is fair use under copyright law?"
- "What are patent infringement remedies?"
- "How do I register a trademark?"

### Business & Tax

- "Can I deduct home office expenses?"
- "What is the corporate tax rate?"
- "How are capital gains taxed?"
- "What business expenses are deductible?"

### Criminal Law

- "What are penalties for wire fraud?"
- "What constitutes insider trading?"
- "What are federal drug penalties?"
- "What is money laundering under federal law?"

### Employment

- "What is the federal minimum wage?"
- "What workplace discrimination is illegal?"
- "What are FMLA leave requirements?"
- "What disability accommodations are required?"

## How It Works

### Step 1: Retrieval

```python
# Your question is embedded using OpenAI
question = "How long does copyright protection last?"

# Top 5 most similar sections retrieved
sections = [
    "17 USC 302: Duration of copyright",
    "17 USC 304: Duration of copyright: Subsisting copyrights",
    ...
]
```

### Step 2: Augmentation

```python
# Sections added as context
prompt = f"""
US CODE SECTIONS:
[17 USC 302] Duration of copyright
(a) In General.—Copyright in a work created on or after
January 1, 1978, subsists from its creation and, except as
provided by the following subsections, endures for a term
consisting of the life of the author and 70 years after
the author's death...

QUESTION: {question}
ANSWER (cite specific sections):
"""
```

### Step 3: Generation

```python
# LLM generates answer using only provided sections
answer = llm.generate(prompt)

# Result:
"Under 17 USC 302, copyright protection for works created
after January 1, 1978 lasts for the life of the author plus
70 years. For works made for hire, anonymous works, and
pseudonymous works, protection lasts 95 years from publication
or 120 years from creation, whichever is shorter (17 USC 302(c))."
```

## API Keys Required

### OpenAI (for embeddings + GPT-4)

```bash
# In .env file
OPENAI_API_KEY=sk-proj-your-key-here
```

### Anthropic (optional, for Claude)

```bash
# In .env file
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## Cost Estimates

### Per Query

**Retrieval (OpenAI embedding):**

- ~$0.0001 per question

**Generation (OpenAI GPT-4):**

- ~$0.01-0.03 per answer (depends on length)

**Generation (Anthropic Claude):**

- ~$0.015-0.04 per answer

**Total: ~$0.01-0.04 per question**

Very affordable for personal use!

## Advanced Usage

### Python API

```python
from app.rag import rag_query

# Get complete result
result = rag_query(
    question="How long does copyright last?",
    provider="openai",  # or "anthropic"
    n_sections=5,  # number of sections to retrieve
    verbose=True  # print progress
)

print(result.answer)
print(f"Used {len(result.sections)} sections")

# Access sources
for section in result.sections:
    print(f"{section.identifier}: {section.heading}")
    print(f"Relevance: {section.relevance:.1%}")
```

### Custom Retrieval

```python
from app.rag import get_relevant_sections

# Get sections without generating answer
sections = get_relevant_sections(
    query="copyright duration",
    n_results=10
)

# Use sections for your own purposes
for s in sections:
    print(s['identifier'], s['text'][:200])
```

## Comparison: Search vs RAG

### Semantic Search (`/search`)

- Returns **raw sections**
- You read and interpret
- See multiple perspectives
- Good for research

### RAG (`/ask`)

- Returns **synthesized answer**
- AI interprets and summarizes
- Cites sources
- Good for specific questions

## Tips for Better Answers

1. **Be specific**: "How long does copyright last?" vs "Tell me about copyright"
2. **Ask one thing**: Don't combine multiple questions
3. **Use legal terminology**: The US Code uses specific terms
4. **Check sources**: Always verify the cited sections
5. **Try both models**: GPT-4 and Claude may give different perspectives

## Limitations

- ❌ **Not legal advice**: AI-generated, for informational purposes only
- ❌ **May miss nuances**: Complex legal topics need professional interpretation
- ❌ **Limited to retrieved sections**: If relevant section isn't retrieved, answer will be incomplete
- ❌ **No case law**: Only covers US Code, not court interpretations
- ❌ **Static data**: Based on your downloaded US Code version

## Troubleshooting

**"Vector database not found"**

```bash
python scripts/processing/create_vector_db.py
```

**"OPENAI_API_KEY not found"**

- Add to `.env` file
- Make sure `.env` is in project root

**"No relevant sections found"**

- Try rephrasing your question
- Use more specific legal terms
- The topic may not be in federal law

**Poor quality answers**

- Try increasing `n_sections` to retrieve more context
- Try different model (GPT-4 vs Claude)
- Rephrase question to be more specific

## Next Steps

- [ ] Add chat history/conversation context
- [ ] Support follow-up questions
- [x] ~~Add citations in answer (inline links)~~ ✅ **Done!** Click [1], [2] markers for popups
- [ ] Export answers as PDF
- [ ] Compare GPT-4 vs Claude side-by-side
- [ ] Add confidence scores
- [ ] Support multi-turn conversations
