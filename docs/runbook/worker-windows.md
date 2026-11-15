# Worker di Windows (TK-005) — laptop model host

Akun Windows khusus pekerja tanpa hak admin. Direktori kerja
`D:\BeosaBasi-work` (izin terbatas). Jangan simpan token di repo.

## Pasang (urutan penting)

1. Driver NVIDIA terbaru (nvidia-smi wajib ada).
2. Python 3.12 + `uv`. Di repo: `cd apps/worker && uv sync`.
3. GPU stack persis dari lock:
   ```
   uv pip install -r requirements.lock
   ```
4. `ffmpeg` + `ffprobe` di PATH (gyan.dev full build).
5. Token baca Hugging Face untuk TK-050: `setx HF_TOKEN <token>` (jendela baru).

## Cek

```
uv run worker doctor
```

Semua baris harus `lulus`: gpu (VRAM bebas ≥5500 MiB),
ffmpeg, torch-cuda, hf-token, battery, workdir.

## Jalan saat masuk

Task Scheduler → jalankan pekerja saat logon (akun pekerja),
kondisi daya: hanya bila colok listrik. Cegah tidur selama job
ditangani pekerja (TK-034), doctor hanya melaporkan status daya.

## WSL2 (cadangan D-16)

Bila `torch-cuda` gagal di Windows asli setelah 2 percobaan bersih,
pindah ke WSL2 + catat di `docs/ADR/`. Jangan campur dua runtime.
