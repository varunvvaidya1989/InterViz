"""Start EnterView, automatically rebuilding the index when local PDFs change."""
import argparse
import hashlib
import json
import sys

from rag.ingest import ROOT, DB_PATH, DATA, build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reindex", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    actual = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "docs").rglob("*.pdf")}
    try:
        saved = json.loads((DATA / "inventory.json").read_text(encoding="utf-8"))
        indexed = {d["path"]: d["sha256"] for d in saved["documents"]}
        for d in saved.get("duplicates", []):
            indexed[d["path"]] = indexed.get(d["same_as"])
    except (FileNotFoundError, ValueError, KeyError):
        indexed = {}
    if args.reindex or not DB_PATH.exists() or actual != indexed:
        print("Building the local source index…", flush=True)
        build()
    from rag.server import main as serve
    if args.open_browser:
        import threading
        import webbrowser
        opener = threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}/"))
        opener.daemon = True
        opener.start()
    sys.argv = [sys.argv[0], "--port", str(args.port)]
    serve()


if __name__ == "__main__":
    main()
