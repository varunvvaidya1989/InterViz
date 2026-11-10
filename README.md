# EnterView — guided interview labs

The implemented founder-controlled GitHub/Docker infrastructure is documented in [automation/README.md](automation/README.md). Development is hosted at [InterViz](https://github.com/varunvvaidya1989/InterViz). This infrastructure does not itself approve a SaaS release plan.

The new SaaS specification and agent delivery pack start at [docs/AGENT_DEVELOPMENT_SYSTEM.md](docs/AGENT_DEVELOPMENT_SYSTEM.md). The initial implementation plan is [docs/plans/M1.md](docs/plans/M1.md). The application below remains the earlier local prototype; SaaS milestone acceptance is tracked separately.

Students follow **Learn → Investigate → Practise → Review**, with a source-grounded tutor beside the lab. The PDF index supports the learning experience.

## Run locally

Python 3.11+ is recommended. From this folder:

```powershell
python -m pip install -r requirements.txt
python start.py
```

Open **http://127.0.0.1:8000/**. Stop the server with Ctrl+C. `start.py` rebuilds the local index when PDFs are added, removed, or changed. To force a rebuild, run `python start.py --reindex`.

On Windows, **double-click `Start-EnterView.cmd`** to start the server and open the learning workspace in your browser.

The source PDFs live in `docs/backend-engg/`. The current corpus has **7 PDFs, 579 pages, 132 contents entries, and 374 question pages**. Ingestion produced 985 searchable passages.

## What is ready

- **One authored guided lab: Caching under pressure.** Three deterministic experiments demonstrate cold/warm reads, stale values, and concurrent refill with/without single-flight. The lab includes original source links, a practice scenario, rehearsal timer, answer drafting, self-review, and an embedded tutor interface.
- **132 source workshops.** Each contents entry becomes a structured reading/investigation/practice/self-review workshop. Guide modules expose their original questions. These templates do not yet have individually authored simulations or validated topic-specific assessments.
- **Source-scoped RAG.** The tutor retrieves only pages belonging to the active lab/workshop before generation. Anthropic-native citations map responses to exact retrieved passages and original PDF pages.
- **Source research workspace.** `knowledge.html` provides locally searchable excerpts, document filters, and standalone tutoring/practice modes. It is secondary to the learning experience.
- **Original demos.** `index.html` still provides the three original animated concept lessons. These run directly from disk without a server.

The product is a local, single-user prototype. Payments, account access, paid bundles, editorial publication, and production hosting have not been implemented. Completion records participation and self-review, not a certified skill level or hiring prediction.

## Hosted tutor

Set `ANTHROPIC_API_KEY` in the **server process environment** and restart the server. Optionally set `ANTHROPIC_MODEL`; the default is `claude-sonnet-4-6`. Never put credentials in JavaScript, source control, URLs, or chat.

The credential available during development was rejected with HTTP 401. **Live hosted generation is therefore not verified.** Search, simulations, answer drafting, self-review, and workshop navigation work independently. Citation integration and UI success/error paths were tested using isolated fixtures, not presented as a successful live model call.

Tutor requests send only retrieved passages, the current question, and up to six recent session messages to the provider. A written practice answer is sent when the student explicitly requests feedback. The app does not persist student answers, chat text, or API requests to disk. Provider retention is governed by the API account's settings and terms. Completion state alone is stored in browser local storage when available.

## Retrieval and extraction

- PyMuPDF extracts text blocks and coordinates; recursive whitespace cuts improve column order heuristically.
- Chunks stay within one page, retain document/unit/question metadata, and use bounded block overlap.
- SQLite FTS5 BM25 ranks title/unit/text matches, with small domain query expansions and page diversification.
- Dense semantic embeddings and learned reranking are **not implemented**. This is a measurable lexical retrieval baseline, not a claim of hybrid vector search.
- Tables and visual diagrams are not semantically interpreted. Original page links remain available for review.
- Salary/counteroffer questions must match salary evidence, preventing HTTP negotiation or saga compensation from being treated as salary advice. No dedicated salary guide is present.
- Original PDFs are unchanged; content ownership/commercial adaptation rights have not been verified.

See `data/CORPUS_AUDIT.md` and `data/inventory.json` for the inventory, contents map, overlap indicators, limitations, and proposed learning paths. Keyword overlap is not an expert assessment of curriculum completeness.

## Development

```powershell
python -m rag.ingest
python -m unittest tests/test_rag.py -v
```

Browser tests in `tests/learning.cjs` use Playwright. Install Playwright in your development environment, then run `node tests/learning.cjs` while the server is running. `ENTERVIEW_URL` optionally changes the server URL. `PLAYWRIGHT_MODULE` can point to an existing Playwright installation, and `CHROMIUM_PATH` can select an existing browser executable.

`tests/smoke.cjs` verifies the original three offline demos. Screenshots are written to `artifacts/`.

## Main files

- `learning.html`, `learning.css`, `learning.js`: learning paths, caching lab, source workshops, and embedded tutor.
- `rag/ingest.py`: PDF ingestion, inventory, and SQLite index.
- `rag/retrieve.py`: retrieval, filtering, and page lookup.
- `rag/workshops.py`: curriculum/source-page scopes.
- `rag/tutor.py`: hosted model integration and citation mapping.
- `rag/server.py`: restricted localhost development server. Only allowlisted public assets and PDFs are served; credentials, Python code, and index files are not exposed as static files.
- `knowledge.*`: secondary document research interface.
- `index.html`, `styles.css`, `content.js`, `app.js`: original animated demos.
