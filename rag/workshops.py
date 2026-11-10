"""Curriculum assembled from source contents, plus an authored caching lab."""
from .retrieve import inventory, source_page


def catalog():
    data = inventory()
    result = [{"id": "caching-under-pressure", "title": "Caching under pressure", "track": "backend", "type": "guided-lab", "description": "Trace stale reads, trigger a cache stampede, and defend your recovery strategy.", "duration": "25–35 min", "source_count": 2}]
    for doc in data["documents"]:
        for unit in doc["units"]:
            result.append({"id": f"{doc['id']}-{unit['number']}", "title": unit["title"], "track": doc["track"], "type": "source-workshop", "description": doc["title"], "document_id": doc["id"], "page": unit["page"], "end": unit["end"], "duration": "Self-paced"})
    return result


def get_workshop(workshop_id):
    data = inventory()
    item = next((w for w in catalog() if w["id"] == workshop_id), None)
    if not item:
        return None
    if workshop_id == "caching-under-pressure":
        backend = next(d for d in data["documents"] if d["track"] == "backend")
        core = next(d for d in data["documents"] if d["title"] == "System Design Core Concepts")
        refs = [(core["id"], 11)] + [(backend["id"], p) for p in range(43, 53)]
    else:
        refs = [(item["document_id"], p) for p in range(item["page"], item["end"] + 1)]
    pages = [source_page(doc_id, page) for doc_id, page in refs]
    pages = [p for p in pages if p]
    # Bounding boxes are retained in the index but are not needed by the learning UI.
    for page in pages:
        page.pop("blocks", None)
    return {**item, "pages": pages, "questions": [p for p in pages if p["question_id"]], "allowed_pages": refs}
