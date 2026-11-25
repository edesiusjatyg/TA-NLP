# QA RAG lokal

Semua kode aplikasi ada di [qa_rag_ollama.ipynb](qa_rag_ollama.ipynb). Notebook hanya membaca `corpus/coba_output/rag_chunks.jsonl`; `manifest.json` tidak diperlukan.

## Persiapan

1. Cek GPU NVIDIA: `nvidia-smi`.
2. Jika Ollama belum terpasang, jalankan installer Linux resmi: `curl -fsSL https://ollama.com/install.sh | sh`.
3. Jalankan server dengan service (`sudo systemctl enable --now ollama`) atau terminal terpisah (`ollama serve`).
4. Unduh model yang dipakai notebook: `ollama pull qwen3:4b-instruct-2507-q4_K_M`.
5. Dari root repo, aktifkan atau buat virtualenv, lalu pasang CPU PyTorch dan dependensi:

```bash
source venv/bin/activate
python -m pip install 'torch>=2.6,<3' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r qa_rag_llm/requirements.txt
python -m pip install ipykernel
python -m ipykernel install --user --name ta-nlp --display-name 'Python (ta-nlp)'
```

## Menjalankan

Jalankan notebook dengan working directory `qa_rag_llm/`. Path proyek memakai `ROOT = Path("..")`. Buka notebook dengan kernel `Python (ta-nlp)`. Jalankan cell chat, lalu ketik `/exit` untuk selesai. E5 multilingual-small berjalan di CPU; Qwen berjalan melalui Ollama.

Untuk evaluasi, siapkan `evaluation/qa_pairs.jsonl` dengan satu JSON per baris dan field `question`, `answers`, `source_pdf_pages`, `answerable`, dan `split`. Set `RUN_EVALUATION = True` dan jalankan cell evaluasi. CSV berisi EM, token F1, page recall@k, halaman konteks, error, serta kolom review manual. EM/F1 dihitung untuk soal yang dapat dijawab; soal tanpa jawaban dinilai melalui review manual.
