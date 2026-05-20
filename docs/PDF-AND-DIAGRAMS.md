# Visualizing TaskForge Architecture in PDF

Markdown PDF tools **do not render Mermaid automatically** in most setups. The diagrams in `README.md` look correct on **GitHub** but may appear as empty code blocks in a PDF unless you use one of the workflows below.

---

## Recommended workflows (easiest first)

### Option 1 — GitHub → Print to PDF (no install)

Best if your repo is on GitHub.

1. Push `README.md` to GitHub.
2. Open the repo — GitHub renders all Mermaid diagrams live.
3. Browser menu → **Print** → **Save as PDF**.
4. Enable “Background graphics” so colors and boxes print correctly.

**Pros:** Zero setup, diagrams match README.  
**Cons:** Long README = long PDF; less control over page breaks.

---

### Option 2 — Mermaid Live Editor (best control per diagram)

Use the source files in `docs/diagrams/*.mmd`.

1. Open [https://mermaid.live](https://mermaid.live).
2. Copy the contents of e.g. `docs/diagrams/01-system-architecture.mmd` into the editor.
3. Menu → **Actions** → **PNG** or **SVG** (SVG scales better in Word/PDF).
4. Save into `docs/images/` (create the folder).
5. Reference images in Markdown:

   ```markdown
   ## System Architecture
   ![System architecture](docs/images/01-system-architecture.png)
   ```

6. Export README to PDF with images embedded (pandoc, Typora, or VS Code “Markdown PDF”).

**Pros:** Sharp diagrams, works in any PDF pipeline.  
**Cons:** Re-export if you change `.mmd` files.

| File | Diagram |
|------|---------|
| `01-system-architecture.mmd` | Components: API, Worker, Postgres, Redis |
| `02-task-lifecycle.mmd` | Task status state machine |
| `03-submit-workflow.mmd` | Submit task sequence |
| `04-worker-workflow.mmd` | Worker processing sequence |

---

### Option 3 — Mermaid CLI (automate all diagrams)

Requires [Node.js](https://nodejs.org/).

```powershell
cd c:\Users\ADMIN\Desktop\taskforge

# One-time: install CLI
npm install -g @mermaid-js/mermaid-cli

# Generate PNGs (run from repo root)
mkdir docs\images -Force
mmdc -i docs/diagrams/01-system-architecture.mmd -o docs/images/01-system-architecture.png -b white
mmdc -i docs/diagrams/02-task-lifecycle.mmd -o docs/images/02-task-lifecycle.png -b white
mmdc -i docs/diagrams/03-submit-workflow.mmd -o docs/images/03-submit-workflow.png -b white
mmdc -i docs/diagrams/04-worker-workflow.mmd -o docs/images/04-worker-workflow.png -b white
```

Then use **pandoc** on a copy of the README that references `docs/images/*.png`, or paste images into Word/Google Docs and export PDF.

---

### Option 4 — VS Code / Cursor “Markdown PDF”

1. Install extension: **Markdown PDF** (`yzane.markdown-pdf`).
2. Mermaid support is limited — often **still blank** unless you embed PNGs (Option 2).
3. Open `README.md` → right-click → **Markdown PDF: Export (pdf)**.

**Tip:** Use Option 2 for diagrams, Option 4 for the rest of the text.

---

### Option 5 — Pandoc + mermaid-filter (advanced)

```powershell
npm install -g @mermaid-js/mermaid-cli
# Install pandoc: https://pandoc.org/installing.html

pandoc README.md -o TaskForge.pdf `
  --filter mermaid-filter `
  -V geometry:margin=1in
```

Requires `mermaid-filter` Python package and Chromium. More setup; good for repeatable doc builds.

---

## Suggested PDF layout (professional)

1. **Cover** — Title, version, date (edit in Word or add YAML title block for pandoc).
2. **§1–2** — Text from README + `01-system-architecture.png`.
3. **§5** — `02-task-lifecycle.png`.
4. **§6** — `03-submit-workflow.png` + `04-worker-workflow.png`.
5. **Remaining sections** — Tables and code from README (no diagrams needed).

---

## Quick checklist

- [ ] Export four PNGs from `docs/diagrams/*.mmd` (Mermaid Live or `mmdc`).
- [ ] Put PNGs in `docs/images/`.
- [ ] Either print from GitHub **or** embed images and run pandoc / Markdown PDF.
- [ ] In print dialog: enable **background graphics**.

---

## Commit images to the repo? (optional)

If you want PDFs to work offline without re-exporting:

```bash
git add docs/images/*.png docs/diagrams/*.mmd
```

Add a short “Architecture figures” subsection in `README.md` with `![...](docs/images/...) ` so GitHub and PDF both show the same pictures.
