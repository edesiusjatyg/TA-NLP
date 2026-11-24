"""Uji integritas dan regresi pada kasus tata letak yang benar-benar bermasalah."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bnpb_corpus.core import (Budget, HAZARDS, build, chunk_units, curate, eligible, extract,
                              normalize, read_json, read_jsonl)
from bnpb_corpus.cli import main


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / "build"
        cls.report = build(ROOT / "data/raw/buku_saku_bnpb.pdf", cls.out, ROOT / "configs", ROOT / "data/curation", Budget())
        cls.units = read_jsonl(cls.out / "evidence_units.jsonl")
        cls.chunks = read_jsonl(cls.out / "rag_chunks.jsonl")
        cls.pages = read_jsonl(cls.out / "pages_raw.jsonl")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def page(self, n):
        return [u for u in self.units if u["pdf_page_start"] == n]

    def test_source_hash_rejects_another_pdf(self):
        path = Path(self.temp.name) / "wrong.pdf"
        path.write_bytes(b"not the pinned book")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            extract(path, read_json(ROOT / "configs/source.json"))

    def test_all_pages_archived_and_all_hazards_present(self):
        self.assertEqual([p["pdf_page"] for p in self.pages], list(range(1, 99)))
        self.assertTrue(HAZARDS <= {h for u in self.units for h in u["hazard_tags"]})

    def test_forms_dividers_and_notes_are_not_knowledge(self):
        pages = {u["pdf_page_start"] for u in self.units}
        self.assertFalse(pages & {1, 2, 4, 5, 8, 9, 15, 63, 70, 81, 93, 94, 95, 96, 97, 98})

    def test_no_false_postdisaster_section(self):
        for u in self.units:
            if set(u["hazard_tags"]) & {"COVID", "KARHUTLA"}:
                self.assertNotIn("PASCA", u["phase_tags"])

    def test_volcano_status_pairs(self):
        rows = [u["table_cells"] for u in self.page(29) if u["table_cells"]]
        self.assertEqual([(x["Level"], x["Status"]) for x in rows], [("IV", "Awas"), ("III", "Siaga"), ("II", "Waspada"), ("I", "Normal")])
        self.assertTrue(all(len(x["Penjelasan"]) > 60 for x in rows))

    def test_rain_table_pairs(self):
        rows = [u["table_cells"] for u in self.page(12) if u["table_cells"]]
        self.assertIn("Desember", rows[0]["Puncak musim hujan"])
        self.assertIn("ekuatorial", rows[1]["Pola dan wilayah"])
        self.assertIn("Oktober", rows[1]["Puncak musim hujan"])

    def test_disability_columns_keep_their_phases(self):
        rows = {u["phase_tags"][0]: u["clean_text"] for u in self.page(69) if u["phase_tags"] != ["UMUM"]}
        self.assertIn("Komunikasi risiko", rows["PRA"])
        self.assertIn("Jauhkan dari lokasi bencana", rows["SAAT"])
        self.assertIn("posko", rows["PASCA"])
        self.assertNotIn("Komunikasi risiko", rows["PASCA"])

    def test_emergency_bag_is_not_mixed_with_graphic_labels(self):
        items = {u["context_label"]: u["clean_text"] for u in self.page(67)}
        self.assertIn("jas hujan", items["Pakaian untuk 3 hari"])
        self.assertNotIn("MASKER", items["Pakaian untuk 3 hari"])
        self.assertNotIn("PAKAIAN GANTI", items["Makanan ringan tahan lama"])
        self.assertEqual(len(self.page(67)), 12)

    def test_dropcap_repairs(self):
        self.assertIn("Tetap di luar gedung", self.page(26)[3]["clean_text"])
        self.assertIn("Terlibat dalam kaporitisasi", self.page(41)[6]["clean_text"])
        self.assertTrue(self.page(35)[4]["clean_text"].endswith("banjir."))

    def test_last_body_lines_not_dropped_as_footer(self):
        self.assertIn("atas jembatan atau rambu-rambu lalu lintas.", self.page(19)[-1]["clean_text"])
        self.assertIn("rambu peringatan bahaya tsunami.", self.page(21)[-1]["clean_text"])
        self.assertIn("kali banjir bandang tiba tanpa peringatan.", self.page(39)[-1]["clean_text"])

    def test_source_errors_are_flagged_without_silent_correction(self):
        lava = next(u for u in self.page(28) if "Aliran lava adalah" in u["clean_text"])
        self.assertIn(">10.000", lava["clean_text"])
        self.assertIn("DUBIOUS_SOURCE", lava["source_quality_flag"])
        self.assertEqual(len([u for u in self.page(56) if "SOURCE_AMBIGUOUS" in u["source_quality_flag"]]), 5)
        incomplete = next(u for u in self.page(62) if "perkantoran atau" in u["clean_text"])
        self.assertIn("INCOMPLETE_SOURCE", incomplete["source_quality_flag"])

    def test_contacts_do_not_swap_names_and_numbers(self):
        police = next(u for u in self.page(84) if u["table_cells"].get("Kontak") == "Polisi")
        self.assertEqual(police["table_cells"]["Informasi kontak dalam buku"], "110")
        self.assertIn("HISTORICAL_RECORD", police["source_quality_flag"])
        provinces = [u for u in self.units if 85 <= u["pdf_page_start"] <= 91]
        self.assertEqual(len(provinces), 34)
        self.assertIn("BPBD Jambi", self.page(85)[3]["clean_text"])
        self.assertIn("0741-670689", self.page(85)[3]["clean_text"])

    def test_sign_labels_and_call_center_are_not_lost(self):
        signs = [u["clean_text"] for u in self.page(82)]
        self.assertIn("Kawasan Rawan Bencana Tsunami", signs)
        self.assertIn("Kawasan Rawan Kekeringan", signs)
        self.assertEqual(self.page(59)[0]["clean_text"], "Call Center 117 & 119")
        self.assertEqual(len(self.page(83)), 9)

    def test_chunks_cover_exact_units_without_crossing_phases(self):
        by_id = {u["evidence_unit_id"]: u for u in self.units}
        seen = []
        for chunk in self.chunks:
            items = [by_id[i] for i in chunk["evidence_unit_ids"]]
            self.assertEqual(chunk["clean_text"], "\n".join(x["clean_text"] for x in items))
            self.assertEqual(len({tuple(x["phase_tags"]) for x in items}), 1)
            self.assertEqual(len({x["pdf_page_start"] for x in items}), 1)
            seen.extend(chunk["evidence_unit_ids"])
        self.assertEqual(sorted(seen), sorted(by_id))

    def test_long_atomic_unit_is_never_silently_truncated(self):
        unit = copy.deepcopy(self.units[0])
        unit["clean_text"] = "jangan hapus syarat penting " * 20
        chunks = chunk_units([unit], Budget(max_words=5))
        self.assertTrue(chunks[0]["exceeds_budget"])
        self.assertEqual(chunks[0]["clean_text"], unit["clean_text"])

    def test_release_rejects_pending_human_review(self):
        with self.assertRaisesRegex(ValueError, "belum disetujui"):
            eligible(self.units, release=True)

    def test_stale_review_is_not_reused(self):
        reviews = {self.units[0]["evidence_unit_id"]: {"content_sha256": "wrong", "decision": "approved"}}
        with self.assertRaisesRegex(ValueError, "kadaluarsa"):
            curate(self.pages, read_json(ROOT / "configs/page_plan.json"), read_json(ROOT / "data/curation/recipes.json"), read_json(ROOT / "configs/source.json"), reviews)

    def test_normalization_keeps_negation_numbers_and_units(self):
        self.assertEqual(normalize("Jangan\nmemakai lensa kontak. Suhu 38°C; eﬁsien."), "Jangan memakai lensa kontak. Suhu 38°C; efisien.")

    def test_build_reproduces_identical_bytes(self):
        other = Path(self.temp.name) / "repeat"
        build(ROOT / "data/raw/buku_saku_bnpb.pdf", other, ROOT / "configs", ROOT / "data/curation", Budget())
        for path in self.out.iterdir():
            self.assertEqual(path.read_bytes(), (other / path.name).read_bytes(), path.name)

    def test_verify_detects_edited_outputs(self):
        other = Path(self.temp.name) / "verify"
        other.mkdir(exist_ok=True)
        for path in self.out.iterdir():
            (other / path.name).write_bytes(path.read_bytes())
        self.assertEqual(main(["--root", str(ROOT), "verify", "--out", str(other)]), 0)
        with (other / "rag_chunks.jsonl").open("a") as f:
            f.write("{}\n")
        self.assertEqual(main(["--root", str(ROOT), "verify", "--out", str(other)]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
