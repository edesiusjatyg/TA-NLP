"""Kasus audit v0.1.1: stale inputs, pengecualian, transaksi, dan path CLI."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bnpb_corpus import core, cli


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.tmp.name) / "fixture"
        for sub in ("configs", "data/curation", "data/raw"):
            shutil.copytree(ROOT / sub, cls.fixture / sub)
        cls.out = cls.fixture / "outputs"
        core.build(cls.fixture / "data/raw/buku_saku_bnpb.pdf", cls.out, cls.fixture / "configs", cls.fixture / "data/curation", core.Budget())
        cls.units = core.read_jsonl(cls.out / "evidence_units.jsonl")
        cls.pages = core.read_jsonl(cls.out / "pages_raw.jsonl")
        cls.chunks = core.read_jsonl(cls.out / "rag_chunks.jsonl")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        shutil.copytree(self.fixture, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def command(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return cli.main(["--root", str(self.root), *args])

    def build(self, **kw):
        return core.build(self.root / "data/raw/buku_saku_bnpb.pdf", self.root / "outputs", self.root / "configs", self.root / "data/curation", core.Budget(), **kw)

    def decision(self, unit=None, **kw):
        unit = unit or self.units[0]
        return {"content_sha256": unit["content_sha256"], "decision": "approved", "reviewer": "Synthetic test reviewer",
                "reviewed_at": "2026-11-24T00:00:00+00:00", "note": "Synthetic test only", **kw}

    def record(self, unit=None, **kw):
        unit = unit or self.units[0]
        core.write_json(self.root / "data/curation/reviews.json", {unit["evidence_unit_id"]: self.decision(unit, **kw)})

    def validate(self, chunks):
        return core.validate(self.pages, core.read_json(self.fixture / "configs/page_plan.json"), self.units, chunks,
                             core.read_json(self.fixture / "configs/source.json"), core.Budget())

    def test_verify_rejects_changed_recipe(self):
        path = self.root / "data/curation/recipes.json"
        path.write_text(path.read_text() + "\n")
        self.assertEqual(self.command("verify"), 2)

    def test_verify_rejects_changed_pdf(self):
        with (self.root / "data/raw/buku_saku_bnpb.pdf").open("ab") as f:
            f.write(b"changed")
        self.assertEqual(self.command("verify"), 2)

    def test_verify_rejects_changed_reviews(self):
        self.record()
        self.assertEqual(self.command("verify"), 2)

    def test_review_rejects_stale_plan(self):
        path = self.root / "configs/page_plan.json"
        plan = core.read_json(path)
        plan[9]["section"] = "Changed section"
        core.write_json(path, plan)
        self.assertEqual(self.command("review", "--unit-id", self.units[0]["evidence_unit_id"], "--decision", "approved",
                                      "--reviewer", "Synthetic", "--note", "Synthetic"), 2)
        self.assertEqual(core.read_json(self.root / "data/curation/reviews.json"), {})

    def test_several_review_decisions_can_be_recorded_before_rebuild(self):
        for unit in self.units[:2]:
            self.assertEqual(self.command("review", "--unit-id", unit["evidence_unit_id"], "--decision", "approved",
                                          "--reviewer", "Synthetic", "--note", "Synthetic"), 0)
        self.assertEqual(len(core.read_json(self.root / "data/curation/reviews.json")), 2)
        self.build()
        self.assertEqual(self.command("verify"), 0)

    def test_excluded_units_are_removed_from_all_knowledge_exports(self):
        unit = self.units[0]
        self.record(decision="excluded")
        self.build()
        out = self.root / "outputs"
        for name in ("classic_passages.jsonl", "rag_chunks.jsonl", "corpus.md", "corpus.txt"):
            self.assertNotIn(unit["evidence_unit_id"], (out / name).read_text())
        self.assertIn(unit["evidence_unit_id"], (out / "evidence_units.jsonl").read_text())
        self.assertIn(unit["evidence_unit_id"], (out / "review.html").read_text())

    def test_validator_rejects_duplicate_chunk(self):
        report = self.validate(self.chunks + [copy.deepcopy(self.chunks[0])])
        self.assertEqual(report["structural_status"], "failed")

    def test_validator_rejects_repeated_unit_under_new_chunk_id(self):
        extra = copy.deepcopy(self.chunks[0])
        extra["chunk_id"] = "different-id"
        self.assertEqual(self.validate(self.chunks + [extra])["structural_status"], "failed")

    def test_support_material_tags_reach_both_systems(self):
        passages = core.read_jsonl(self.out / "classic_passages.jsonl")
        self.assertTrue(any(u["material_tags"] == ["DISABILITAS"] for u in passages))
        self.assertTrue(any(u["material_tags"] == ["DISABILITAS"] for u in self.chunks))

    def test_write_failure_preserves_complete_previous_build(self):
        old = {p.name: p.read_bytes() for p in (self.root / "outputs").iterdir()}
        actual = core.write_jsonl
        def fail(path, rows):
            if path.name == "rag_chunks.jsonl":
                raise OSError("Synthetic disk write failure")
            return actual(path, rows)
        with patch.object(core, "write_jsonl", side_effect=fail):
            with self.assertRaisesRegex(OSError, "Synthetic"):
                self.build()
        self.assertEqual(old, {p.name: p.read_bytes() for p in (self.root / "outputs").iterdir()})
        self.assertEqual(self.command("verify"), 0)

    def test_nested_output_under_input_folder_is_rejected(self):
        for out in (self.root / "data/raw/generated", self.root / "configs/generated", self.root):
            with self.assertRaisesRegex(ValueError, "Folder output"):
                core.build(self.root / "data/raw/buku_saku_bnpb.pdf", out, self.root / "configs", self.root / "data/curation", core.Budget())
            self.assertFalse((out / "pages_raw.jsonl").exists())

    def test_unmanaged_output_folder_is_not_overwritten(self):
        out = self.root / "unrelated"
        out.mkdir()
        (out / "corpus.txt").write_text("user file")
        with self.assertRaisesRegex(ValueError, "bukan hasil build"):
            core.build(self.root / "data/raw/buku_saku_bnpb.pdf", out, self.root / "configs", self.root / "data/curation", core.Budget())
        self.assertEqual((out / "corpus.txt").read_text(), "user file")

    def test_manifest_does_not_claim_unrelated_files_as_generated(self):
        out = self.root / "outputs"
        (out / "personal-note.txt").write_text("keep")
        self.build()
        self.assertEqual((out / "personal-note.txt").read_text(), "keep")
        self.assertNotIn("personal-note.txt", core.read_json(out / "build_manifest.json")["files"])
        self.assertEqual(self.command("verify"), 0)

    def test_review_decision_typo_is_rejected(self):
        self.record(decision="aproved")
        with self.assertRaisesRegex(ValueError, "Keputusan review"):
            self.build()

    def test_accepted_flags_must_be_an_array_not_string(self):
        self.record(accepted_flags="DUBIOUS_SOURCE")
        with self.assertRaisesRegex(ValueError, "accepted_flags"):
            self.build()

    def test_phase_typo_is_rejected(self):
        path = self.root / "configs/page_plan.json"
        plans = core.read_json(path)
        plans[15]["default_phase"] = "PRRA"
        core.write_json(path, plans)
        with self.assertRaisesRegex(ValueError, "fase tidak valid"):
            self.build()

    def test_quality_flag_typo_is_rejected(self):
        path = self.root / "configs/page_plan.json"
        plans = core.read_json(path)
        plans[15]["quality_flags"] = ["DUBIOUS_SOURC"]
        core.write_json(path, plans)
        with self.assertRaisesRegex(ValueError, "Flag kualitas"):
            self.build()

    def test_page_zero_does_not_silently_match_all_pages(self):
        self.assertEqual(self.command("inspect", "--page", "0"), 2)

    def test_render_refuses_unpinned_pdf(self):
        with (self.root / "data/raw/buku_saku_bnpb.pdf").open("ab") as f:
            f.write(b"changed")
        self.assertEqual(self.command("render-pages", "--pages", "1"), 2)

    def test_custom_output_html_links_to_actual_pdf(self):
        out = self.root / "nested/review"
        core.build(self.root / "data/raw/buku_saku_bnpb.pdf", out, self.root / "configs", self.root / "data/curation", core.Budget())
        self.assertIn("../../data/raw/buku_saku_bnpb.pdf#page=", (out / "review.html").read_text())


@unittest.skipUnless(importlib.util.find_spec("transformers"), "Optional tokenizer dependencies not installed")
class TokenizerAuditTests(unittest.TestCase):
    def test_local_snapshot_identity_has_revision_and_content_fingerprint(self):
        budget = core.Budget(tokenizer_name=str(ROOT / "data/tokenizers/multilingual-e5-small"), local_only=True)
        spec = budget.config()
        self.assertEqual(spec["tokenizer_name"], "intfloat/multilingual-e5-small")
        self.assertEqual(len(spec["tokenizer_revision"]), 40)
        self.assertEqual(len(spec["tokenizer_fingerprint"]), 64)

    def test_cli_build_from_other_working_directory_with_relative_tokenizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / "corpus.py"), "build", "--out", str(Path(tmp) / "build"),
                                     "--tokenizer", "data/tokenizers/multilingual-e5-small", "--local-only"],
                                    cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["token_limit_verified"])
            self.assertFalse(report["oversized_chunks"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
