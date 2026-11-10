"""Build a page-cited SQLite knowledge base and a reviewable content inventory.

Run: python -m rag.ingest
Original PDFs are never modified. No content is sent to an external service.
"""
import argparse
import hashlib
import json
import re
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB_PATH = DATA / "knowledge.sqlite3"
CATALOG = {
    "backend-interview": ("Backend Interview Playbook", "backend", "guide"),
    "0313dad": ("DevOps Interview Playbook", "devops", "guide"),
    "ac4051": ("Software Engineer to AI Engineer Interview Guide", "ai-engineering", "guide"),
    "system-design-core": ("System Design Core Concepts", "system-design", "concepts"),
    "hld-interview": ("High-Level Design Problems", "system-design", "problems"),
    "lld-core": ("LLD Core Concepts", "low-level-design", "concepts"),
    "lld-design": ("Low-Level Design Problems", "low-level-design", "problems"),
}
TOPICS = {
    "caching": ["cache", "caching", "redis", "stampede", "eviction"],
    "databases": ["database", "sql", "postgres", "transaction", "indexing", "isolation"],
    "messaging": ["kafka", "queue", "consumer", "idempotency", "pub-sub"],
    "reliability": ["retry", "circuit breaker", "incident", "slo", "recovery"],
    "networking": ["dns", "tcp", "http", "load balancing", "tls"],
    "security": ["authorization", "authentication", "security", "secrets", "injection"],
    "ownership": ["ownership", "personally", "conflict", "behavioural", "reflection"],
    "rag": ["retrieval", "embedding", "rerank", "grounding", "chunking"],
    "design-patterns": ["solid", "factory", "strategy", "observer", "inheritance"],
    "operations": ["kubernetes", "container", "deployment", "pipeline", "gitops"],
    "negotiation": ["salary", "counteroffer", "salary negotiation", "offer negotiation", "recruiter"],
}


def clean(text):
    return re.sub(r"[ \t]+", " ", text.replace("\x00", "").replace("\u00ad", "")).strip()


def toc_units(text, kind):
    if kind == "guide":
        pattern = r"(?:^|\n)(\d{2})\n(.+?)\n\d+ questions[^\n]*\npp\.\s*(\d+)\s*[–−-]\s*(\d+)"
    else:
        pattern = r"(?:^|\n)(\d{2})\n(.+?)\np\.\s*(\d+)(?:\s*[–−-]\s*(\d+))?(?=\n|$)"
    units = []
    for m in re.finditer(pattern, text, re.S | re.I):
        title = " ".join(m[2].split())
        title = re.sub(r" (Foundation|Principle|Comparison|Notation|Framework|Creational|Structural|Behavioural)$", "", title)
        units.append({"number": int(m[1]), "title": title, "page": int(m[3]), "end": int(m[4] or m[3])})
    return units


def reading_order(blocks):
    """Recursive whitespace cuts keep nearby columns together when possible.

    This is a text-only heuristic, not visual understanding of tables or diagrams.
    Original bounding boxes remain stored for later parser improvements.
    """
    if len(blocks) < 2:
        return blocks
    choices = []
    for axis, minimum in [(0, 12), (1, 9)]:
        ordered = sorted(blocks, key=lambda b: b[axis])
        end = ordered[0][axis + 2]
        for i, block in enumerate(ordered[1:], 1):
            gap = block[axis] - end
            if gap >= minimum:
                choices.append((gap / (2 if axis == 1 else 1), ordered[:i], ordered[i:]))
            end = max(end, block[axis + 2])
    if choices:
        _, left, right = max(choices, key=lambda c: c[0])
        return reading_order(left) + reading_order(right)
    return sorted(blocks, key=lambda b: (round(b[1] / 8), b[0]))


def page_blocks(page, repeated):
    blocks = []
    for b in page.get_text("blocks"):
        if len(b) > 6 and b[6] != 0:
            continue
        text = clean(b[4])
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        lines = [line for line in lines if line not in repeated and not re.fullmatch(r"(?:Page \d+ of \d+|H/|helpmeswitch\.in)", line, re.I) and not (b[1] > page.rect.height * .94 and line.isdigit())]
        if not lines:
            continue
        blocks.append((*b[:4], "\n".join(lines)))
    return reading_order(blocks)


def chunk_blocks(blocks, max_words=440, overlap=65):
    chunks, group, words = [], [], 0
    for b in blocks:
        text = b[4]
        # Split unusually large text objects at word boundaries.
        pieces = [text] if len(text.split()) <= max_words else [" ".join(text.split()[i:i + max_words]) for i in range(0, len(text.split()), max_words)]
        for piece in pieces:
            count = len(piece.split())
            if group and words + count > max_words:
                chunks.append("\n\n".join(group))
                tail, tail_words = [], 0
                for old in reversed(group):
                    if tail_words + len(old.split()) > overlap:
                        break
                    tail.insert(0, old)
                    tail_words += len(old.split())
                group, words = tail, tail_words
            group.append(piece)
            words += count
    if group:
        chunks.append("\n\n".join(group))
    return chunks


def page_heading(raw, fallback):
    match = re.search(r"(?:^|\n)(Q\d+\.\d+)\s*\n(.*?)(?:\nWHAT IT REALLY|\n!|\nWEAK ANSWER)", raw, re.S)
    if match:
        return match[1], " ".join(match[2].split())
    return "", fallback


def build(source=ROOT / "docs"):
    source = Path(source).resolve()
    files = sorted(source.rglob("*.pdf"))
    if not files:
        raise ValueError(f"No PDFs found in {source}")
    DATA.mkdir(exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="knowledge-", suffix=".tmp", dir=DATA)
    import os
    os.close(fd)
    db = sqlite3.connect(temp_name)
    db.executescript("""
        CREATE TABLE documents(id TEXT PRIMARY KEY,title TEXT,path TEXT,track TEXT,kind TEXT,sha256 TEXT,page_count INTEGER,units TEXT);
        CREATE TABLE pages(doc_id TEXT,page INTEGER,title TEXT,unit TEXT,question_id TEXT,text TEXT,blocks TEXT,topics TEXT,PRIMARY KEY(doc_id,page));
        CREATE TABLE chunks(id INTEGER PRIMARY KEY,doc_id TEXT,page INTEGER,title TEXT,unit TEXT,question_id TEXT,text TEXT,topics TEXT);
        CREATE VIRTUAL TABLE search USING fts5(title,unit,text,content='chunks',content_rowid='id',tokenize='porter unicode61');
        CREATE INDEX chunk_page ON chunks(doc_id,page);
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
    """)
    documents, warnings, duplicate_files = [], [], []
    seen, topic_docs = {}, defaultdict(set)
    try:
        for path in files:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in seen:
                duplicate_files.append({"path": path.relative_to(ROOT).as_posix(), "same_as": seen[digest]})
                continue
            relative = path.relative_to(ROOT).as_posix()
            seen[digest] = relative
            with pymupdf.open(path) as pdf:
                first = pdf[0].get_text()
                default_title = pdf.metadata.get("title") or path.stem
                title, track, kind = next((value for prefix, value in CATALOG.items() if path.name.startswith(prefix)), (default_title, "other", "document"))
                doc_id = hashlib.sha256(relative.encode()).hexdigest()[:16]
                units = toc_units(pdf[1].get_text(), kind) if len(pdf) > 1 else []
                raw_pages = [p.get_text() for p in pdf]
                repeated_lines = Counter(line.strip() for raw in raw_pages for line in raw.splitlines() if len(line.strip()) > 3)
                repeated = {line for line, count in repeated_lines.items() if count >= max(8, len(pdf) * .65) and len(line) < 100}
                # Preserve repeated pedagogical headings; remove only known document furniture.
                repeated &= {title, default_title, "HelpMeSwitch", "helpmeswitch.in"}
                db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)", (doc_id, title, relative, track, kind, digest, len(pdf), json.dumps(units)))
                info = {"id": doc_id, "title": title, "path": relative, "track": track, "kind": kind, "sha256": digest, "pages": len(pdf), "units": units, "questions": 0, "chunks": 0, "text_pages": 0, "words": 0, "low_text_pages": []}
                for i, page in enumerate(pdf, 1):
                    raw = raw_pages[i - 1]
                    blocks = page_blocks(page, repeated)
                    text = "\n\n".join(b[4] for b in blocks)
                    if len(raw.strip()) < 80:
                        info["low_text_pages"].append(i)
                    else:
                        info["text_pages"] += 1
                    unit = next((u["title"] for u in units if u["page"] <= i <= u["end"]), "")
                    question_id, heading = page_heading(raw, unit or title)
                    if question_id:
                        info["questions"] += 1
                    topics = [topic for topic, terms in TOPICS.items() if any(term in text.lower() for term in terms)]
                    for topic in topics:
                        topic_docs[topic].add(title)
                    info["words"] += len(text.split())
                    db.execute("INSERT INTO pages VALUES(?,?,?,?,?,?,?,?)", (doc_id, i, heading, unit, question_id, text, json.dumps(blocks), json.dumps(topics)))
                    # Exclude covers, contents, final marketing pages, and empty pages.
                    content_page = any(u["page"] <= i <= u["end"] for u in units) if units else i > 2
                    if not content_page or len(text.split()) < 35:
                        continue
                    for chunk in chunk_blocks(blocks):
                        cursor = db.execute("INSERT INTO chunks(doc_id,page,title,unit,question_id,text,topics) VALUES(?,?,?,?,?,?,?)", (doc_id, i, heading, unit, question_id, chunk, json.dumps(topics)))
                        db.execute("INSERT INTO search(rowid,title,unit,text) VALUES(?,?,?,?)", (cursor.lastrowid, heading, unit, chunk))
                        info["chunks"] += 1
                if info["low_text_pages"]:
                    warnings.append({"document": title, "pages": info["low_text_pages"], "reason": "Low extracted text; may need OCR or visual review."})
                if not units:
                    warnings.append({"document": title, "reason": "No recognised table of contents; generic page indexing used."})
                documents.append(info)
                print(f"Indexed {title}: {info['pages']} pages, {info['chunks']} chunks, {info['questions']} question pages")
        built_at = datetime.now(timezone.utc).isoformat()
        total = {"documents": len(documents), "pages": sum(d["pages"] for d in documents), "chunks": sum(d["chunks"] for d in documents), "units": sum(len(d["units"]) for d in documents), "questions": sum(d["questions"] for d in documents), "words": sum(d["words"] for d in documents)}
        inventory = {"built_at": built_at, "retrieval": "SQLite FTS5 BM25 with title weighting, query expansion and page diversification; no dense embeddings yet", "totals": total, "documents": documents, "overlap": {k: sorted(v) for k, v in topic_docs.items()}, "warnings": warnings, "duplicates": duplicate_files, "limitations": ["Text extraction preserves block coordinates but does not interpret visual diagrams or guarantee table reading order.", "No dedicated salary-negotiation guide identified; keyword mentions are not evidence of a complete curriculum.", "Source examples and model answers must not be presented as the learner's own experience.", "Content ownership and commercial adaptation rights have not been verified."]}
        db.execute("INSERT INTO metadata VALUES('inventory',?)", (json.dumps(inventory),))
        db.commit()
        db.close()
        Path(temp_name).replace(DB_PATH)
        (DATA / "inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
        write_report(inventory)
        print("TOTAL", json.dumps(total))
        return inventory
    except Exception:
        db.close()
        Path(temp_name).unlink(missing_ok=True)
        raise


def write_report(inventory):
    t = inventory["totals"]
    lines = ["# EnterView corpus audit", "", f"Built {inventory['built_at']}. {t['documents']} unique PDFs, {t['pages']} pages, {t['chunks']} text chunks, {t['units']} contents entries, {t['questions']} question pages.", "", "## Documents", "", "| Document | Track | Pages | Contents entries | Question pages | Chunks |", "|---|---|---:|---:|---:|---:|"]
    lines += [f"| {d['title']} | {d['track']} | {d['pages']} | {len(d['units'])} | {d['questions']} | {d['chunks']} |" for d in inventory["documents"]]
    lines += ["", "## Cross-document topic overlap", "", "These are keyword-based coverage indicators, not an expert assessment of completeness.", ""]
    lines += [f"- **{topic}**: {'; '.join(docs)}" for topic, docs in sorted(inventory["overlap"].items())]
    lines += ["", "## Proposed learning paths", "", "1. **Backend foundations:** system-design concepts → API and database modules → caching and messaging → reliability and incident drills.", "2. **Design interviews:** coupling and SOLID → design patterns → LLD problems → HLD problems → backend blank-page design module.", "3. **Ownership and behavioural:** backend project deep dives → behavioural/managerial module → DevOps ownership module → timed personal-story practice.", "4. **Production engineering:** Linux/networking → containers and CI/CD → Kubernetes/IaC → observability → incident recovery.", "5. **AI engineering:** LLM foundations → context engineering → retrieval architecture → retrieval failure diagnosis → evaluation → agents → AI system design.", "", "Prerequisites and lab quality require editorial review before these become paid bundles.", "", "## Extraction and product gaps", ""]
    lines += [f"- {item}" for item in inventory["limitations"]]
    lines += [f"- {w['document']}: {w['reason']} {w.get('pages', '')}" for w in inventory["warnings"]]
    lines += ["", "## Source map", ""]
    for d in inventory["documents"]:
        lines += [f"### {d['title']}", "", f"Source: `{d['path']}`", ""]
        lines += [f"- pp. {u['page']}–{u['end']}: {u['title']}" for u in d["units"]]
        lines.append("")
    (DATA / "CORPUS_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs")
    build(parser.parse_args().source)
