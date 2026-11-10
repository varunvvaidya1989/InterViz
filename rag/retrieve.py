"""Inspectable, page-aware BM25 retrieval. Dense embeddings are a future upgrade."""
import json
import re
import sqlite3
from contextlib import contextmanager
from urllib.parse import quote

from .ingest import DB_PATH

STOP = set("a an and are as at be been being but by can could did do does for from give had has have how i if in into is it its me my of on or our please should show some tell than that the their them there these they this to us use using want was we were what when where which who why will with would you your explain understand describe help example examples answer question about between".split())
EXPAND = {
    "stale": ["cache", "ttl", "invalidation"],
    "stampede": ["thundering", "herd", "single-flight"],
    "behavioral": ["behavioural", "ownership"],
    "behavioural": ["behavioral", "ownership"],
    "salary": ["negotiation", "compensation", "counteroffer"],
    "negotiate": ["negotiation", "salary"],
    "rag": ["retrieval", "chunking", "grounding"],
    "k8s": ["kubernetes"],
    "duplicates": ["idempotency", "deduplication"],
    "oop": ["solid", "coupling", "inheritance"],
    "fairness": ["weighted", "balancing"],
    "retries": ["retry", "backoff", "jitter"],
    "star": ["behavioural", "ownership", "reflection"],
}


@contextmanager
def connect():
    if not DB_PATH.exists():
        raise FileNotFoundError("Knowledge base not built. Run: python -m rag.ingest")
    db = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def inventory():
    with connect() as db:
        return json.loads(db.execute("SELECT value FROM metadata WHERE key='inventory'").fetchone()[0])


def terms_for(query):
    terms = list(dict.fromkeys(t for t in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", query.lower()) if t not in STOP and len(t) > 1))[:24]
    expanded = list(dict.fromkeys(terms + [word for term in terms for word in EXPAND.get(term, [])]))
    return terms, expanded[:40]


def coverage(terms, text):
    lowered = text.lower()
    return sum(bool(re.search(r"\b" + re.escape(t[:max(3, len(t)-2)]), lowered)) for t in terms) / max(1, len(terms))


def snippet(text, terms, size=850):
    lower = text.lower()
    matches = [lower.find(t) for t in terms if t in lower]
    start = max(0, (min(matches) if matches else 0) - 140)
    if start:
        boundary = text.find(" ", start)
        start = boundary + 1 if boundary >= 0 else start
    return ("…" if start else "") + text[start:start+size] + ("…" if len(text) > start+size else "")


def search(query, doc_ids=None, track=None, limit=8, allowed_pages=None):
    if not isinstance(query, str) or len(query) > 2000:
        raise ValueError("Search must be text of at most 2,000 characters.")
    terms, expanded = terms_for(query)
    if not terms:
        return []
    # Operators come only from code; user input is tokenised and quoted.
    expression = " OR ".join('"' + t.replace('"', '') + '"' for t in expanded)
    conditions, params = ["search MATCH ?"], [expression]
    if doc_ids is not None:
        if not doc_ids:
            return []
        conditions.append("c.doc_id IN (" + ",".join("?" for _ in doc_ids) + ")")
        params.extend(doc_ids)
    if track:
        conditions.append("d.track = ?")
        params.append(track)
    if allowed_pages is not None:
        if not allowed_pages:
            return []
        conditions.append("(" + " OR ".join("(c.doc_id=? AND c.page=?)" for _ in allowed_pages) + ")")
        for doc_id, page in allowed_pages:
            params.extend([doc_id, page])
    sql = """SELECT c.*,d.title AS document_title,d.path,d.track,
        bm25(search,5.0,3.0,1.0) AS rank
        FROM search JOIN chunks c ON c.id=search.rowid
        JOIN documents d ON d.id=c.doc_id WHERE """ + " AND ".join(conditions) + " ORDER BY rank LIMIT 100"
    with connect() as db:
        candidates = [dict(r) for r in db.execute(sql, params)]
    if not candidates:
        return []
    strongest = max(-r["rank"] for r in candidates) or 1
    for r in candidates:
        text = r["title"] + " " + r["unit"] + " " + r["text"]
        r["term_coverage"] = coverage(terms, text)
        r["score"] = round(.55*(-r["rank"]/strongest) + .35*r["term_coverage"] + .1*coverage(terms, r["title"]+" "+r["unit"]), 4)
    candidates.sort(key=lambda r: r["score"], reverse=True)
    selected, pages = [], set()
    for r in candidates:
        key = (r["doc_id"], r["page"])
        # "Compensation" in a saga and HTTP "negotiation" are not salary evidence.
        if any(t in terms for t in ("salary", "counteroffer")) and not re.search(r"\b(salary|counteroffer|recruiter|pay band|offer letter)\b", r["text"], re.I):
            continue
        if key in pages:
            continue
        # Avoid presenting a match on one incidental word as strong multi-term evidence.
        if r["term_coverage"] < .20 and not any(t in EXPAND and coverage(EXPAND[t], r["text"]) > .3 for t in terms):
            continue
        pages.add(key)
        r["url"] = "/" + quote(r.pop("path"), safe="/") + f"#page={r['page']}"
        r["snippet"] = snippet(r["text"], terms)
        r["topics"] = json.loads(r["topics"])
        r.pop("rank", None)
        selected.append(r)
        if len(selected) >= max(1, min(limit, 20)):
            break
    return selected


def source_page(doc_id, page):
    with connect() as db:
        row = db.execute("SELECT p.*,d.title AS document_title,d.path FROM pages p JOIN documents d ON d.id=p.doc_id WHERE p.doc_id=? AND p.page=?", (doc_id, page)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["blocks"] = json.loads(result["blocks"])
    result["topics"] = json.loads(result["topics"])
    result["url"] = "/" + quote(result.pop("path"), safe="/") + f"#page={page}"
    return result
