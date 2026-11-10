import json
import os
import unittest
from unittest.mock import patch

from rag.ingest import chunk_blocks, toc_units
from rag.retrieve import connect, inventory, search, source_page
from rag.tutor import ProviderError, generate
from rag.workshops import catalog, get_workshop


class RetrievalTests(unittest.TestCase):
    def test_complete_inventory(self):
        data = inventory()
        self.assertEqual(data["totals"]["documents"], 7)
        self.assertEqual(data["totals"]["pages"], 579)
        self.assertEqual(data["totals"]["questions"], 374)
        self.assertEqual(len(catalog()), 133)
        self.assertTrue(all(d["units"] for d in data["documents"]))

    def test_golden_retrieval(self):
        cases = [
            ("cache stampede thundering herd", "backend", "stampede"),
            ("cache stale invalidation", "backend", "cache"),
            ("Kafka consumer offset rebalance", "backend", "Kafka"),
            ("transaction isolation deadlock", "backend", "Databases"),
            ("behavioural conflict ownership", "backend", "Behavioural"),
            ("production RAG pipeline chunking", "ai-engineering", "RAG"),
            ("retrieval quality evaluation", "ai-engineering", "RAG"),
            ("parking lot design", "low-level-design", "Parking"),
            ("SOLID dependency inversion", "low-level-design", "SOLID"),
            ("load balancing round robin", "system-design", "Load Balancing"),
            ("URL shortener", "system-design", "URL"),
            ("Kubernetes CrashLoopBackOff", "devops", "Kubernetes"),
        ]
        for query, track, expected in cases:
            with self.subTest(query=query):
                rows = search(query, track=track, limit=5)
                self.assertTrue(rows)
                self.assertTrue(any(expected.lower() in (r["unit"] + " " + r["title"]).lower() for r in rows), [(r["page"], r["title"]) for r in rows])

    def test_citations_resolve(self):
        for row in search("cache stale invalidation", limit=8):
            page = source_page(row["doc_id"], row["page"])
            self.assertIsNotNone(page)
            self.assertIn(row["text"].splitlines()[0], page["text"])
            self.assertTrue(row["url"].endswith(f"#page={row['page']}"))

    def test_out_of_scope_and_empty_queries(self):
        self.assertEqual(search("salary negotiation counteroffer"), [])
        self.assertEqual(search("zzzzzz astrophotonic zzzzzz"), [])
        self.assertEqual(search("how do I"), [])
        self.assertEqual(search("cache", doc_ids=[]), [])
        self.assertEqual(search("cache", doc_ids=["does-not-exist"]), [])
        self.assertEqual(search('" OR 1=1 --'), [])

    def test_workshop_scope_precedes_retrieval(self):
        workshop = get_workshop("caching-under-pressure")
        allowed = {tuple(p) for p in workshop["allowed_pages"]}
        results = search("cache invalidation database", allowed_pages=workshop["allowed_pages"])
        self.assertTrue(results)
        self.assertTrue(all((r["doc_id"], r["page"]) in allowed for r in results))
        self.assertEqual(search("Kubernetes", allowed_pages=[]), [])
        self.assertIsNone(get_workshop("missing"))

    def test_chunk_boundary_and_contents_parser(self):
        chunks = chunk_blocks([(0, 0, 10, 10, "first block " * 100), (0, 12, 10, 20, "second block " * 100)], max_words=300)
        self.assertEqual(len(chunks), 2)
        units = toc_units("01\nCaching\np.3–5\n02\nQueues\np.6–8\n", "problems")
        self.assertEqual([(u["title"], u["page"], u["end"]) for u in units], [("Caching", 3, 5), ("Queues", 6, 8)])


class ProviderTests(unittest.TestCase):
    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError):
                generate("Explain caching")

    def test_native_citations_are_mapped_and_invalid_ones_dropped(self):
        source = {"text": "A cache keeps a fast copy.", "document_title": "Source", "page": 11, "title": "Caching", "url": "/docs/source.pdf#page=11"}
        payload = {"content": [{"type": "text", "text": "A cache is a fast copy.", "citations": [{"document_index": 0, "cited_text": source["text"]}, {"document_index": 100}, {"document_index": 0, "cited_text": "not in the source"}]}], "usage": {}, "stop_reason": "end_turn", "model": "test-model"}

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps(payload).encode()

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only-placeholder"}), patch("rag.tutor.search", return_value=[source]) as retrieval, patch("rag.tutor.urllib.request.urlopen", return_value=FakeResponse()) as request:
            result = generate("Explain caching", allowed_pages=[("doc", 11)])
            self.assertEqual(result["citation_count"], 1)
            self.assertEqual(result["blocks"][0]["citations"][0]["page"], 11)
            self.assertEqual(retrieval.call_args.kwargs["allowed_pages"], [("doc", 11)])
            body = json.loads(request.call_args.args[0].data)
            self.assertTrue(body["messages"][0]["content"][0]["citations"]["enabled"])

    def test_unsupported_subject_does_not_call_model(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only-placeholder"}), patch("rag.tutor.urllib.request.urlopen") as request:
            result = generate("salary negotiation counteroffer")
            self.assertFalse(result["generated"])
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
