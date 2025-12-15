# US Laws Project - File Formats Guide

## 📦 File Formats Explained

When downloading US Code, you'll see 4 formats:

### 1. **XML** (Recommended ✅)

- **Size**: ~2.5 GB
- **Format**: USLM XML (United States Legislative Markup)
- **Best for**: Machine parsing, search, display on websites
- **Structure**:
  ```xml
  <title>
    <chapter>
      <section>
        <identifier>5 USC 101</identifier>
        <heading>Definitions</heading>
        <content>...</content>
      </section>
    </chapter>
  </title>
  ```
- **Use**: Easy to parse with `parse_uscode.py`

### 2. **XHTML**

- **Size**: ~3 GB
- **Format**: Pre-formatted HTML
- **Best for**: Viewing in browser directly
- **Downside**: Larger, harder to customize

### 3. **PCC**

- **Size**: ~1 GB
- **Format**: GPO typesetting codes
- **Best for**: Professional printing
- **Downside**: Legacy format, hard to read/parse

### 4. **PDF**

- **Size**: ~5 GB
- **Format**: Adobe PDF
- **Best for**: Printing, offline reading
- **Downside**: Can't parse or search programmatically

---

## 🎯 What to Download

**For your website: Use XML only**

```bash
# Download just one title to test
python download_full_code.py
# Choose option 2 (sample)

# Download everything
python download_full_code.py
# Choose option 1 (full)
```

---

## 📁 Project Structure After Download

```
us-laws/
├── app.py                      # Web viewer (updated)
├── parse_uscode.py             # XML parser
├── download_full_code.py       # Downloader
├── us_public_laws.csv          # 20,976 laws
├── us_code_titles.csv          # 54 titles
└── data/
    ├── uscode/                 # Downloaded code
    │   ├── title_01/           # Title 1: General Provisions
    │   │   └── *.xml files
    │   ├── title_18/           # Title 18: Crimes
    │   │   └── *.xml files
    │   ├── title_26/           # Title 26: Tax Code
    │   │   └── *.xml files
    │   └── ... (54 titles)
    └── founding_documents/
        ├── constitution.txt
        ├── declaration_of_independence.txt
        ├── articles_of_confederation.txt
        └── northwest_ordinance.txt
```

---

## 🚀 How to Use

### 1. Start with a sample (fast)

```bash
python download_full_code.py
# Choose option 2
# Downloads: Titles 1, 18, 26 (~400 MB, 5 minutes)
```

### 2. Run the web viewer

```bash
python -m app.main
# Visit: http://localhost:8000
```

### 3. Navigate:

- **Home**: Overview stats
- **Public Laws**: Browse 20,976 laws (1951-2024)
- **US Code**: View titles → Click "View" → See sections

### 4. Search within titles

- Click any title number
- Use search box to find sections
- View section text, headings, identifiers

---

## 🔍 How XML Parsing Works

The `parse_uscode.py` script:

1. **Reads XML files** in `data/uscode/title_XX/`
2. **Extracts sections** with:
   - Identifier (e.g., "5 USC 101")
   - Heading (e.g., "Definitions")
   - Full text content
   - Notes/amendments
3. **Returns clean text** for display
4. **Caches results** for performance

---

## 💡 Tips

### Performance

- XML parsing is fast for 1 title
- For all 54 titles, parse on-demand (not all at once)
- Cache parsed sections in memory

### Display

- Show 50 sections per page
- Truncate long text to ~300 chars with "read more"
- Add pagination for better UX

### Storage

- XML: ~2.5 GB compressed, ~8 GB uncompressed
- Keep zips if you want to re-extract later
- Each title is independent (can download separately)

---

## 🎨 Website Features

Current features:

- ✅ Browse 20,976 public laws
- ✅ View US Code structure (54 titles)
- ✅ Click to view individual titles
- ✅ Semantic search across all titles
- ✅ Display section text
- ✅ AI-powered Q&A with GPT-4o and Claude

To add:

- [x] Full-text search across all titles
- [x] Founding documents pages
- [ ] Links between laws and code sections
- [ ] Download/export sections as PDF
- [ ] Historical versions (prior release points)

---

## 📖 Founding Documents

Founding documents are stored as text files in `data/founding_documents/`.

Included documents:

- **Declaration of Independence** (1776)
- **Articles of Confederation** (1777)
- **Northwest Ordinance** (1787)
- **Constitution** (1787)
- **Bill of Rights** (1791) - Includes all 27 Amendments

These are fetched automatically using `scripts/download/fetch_founding_docs.py`.

---

## 🛠️ Next Steps

1. **Test with sample data** (3 titles)
2. **Verify XML parsing works**
3. **Check website display**
4. **Download full dataset** (if satisfied)
5. **Add founding documents manually**
6. **Customize styling** to your preference
