"""Versioned SQLite migrations for TK-020 (PRD 4.4).

Single source of truth: MIGRATIONS = [(version, up_sql, down_sql)].
Applied by api.db.migrate() with a schema_migrations ledger table.
"""

MIGRATION_001_UP = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  google_sub TEXT UNIQUE,
  status TEXT NOT NULL DEFAULT 'aktif'
    CHECK (status IN ('aktif', 'dinonaktifkan')),
  dibuat_pada TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS allowlist (
  email TEXT PRIMARY KEY,
  ditambahkan_pada TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consents (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  versi_dokumen TEXT NOT NULL,
  diberikan_pada TEXT NOT NULL,
  ditarik_pada TEXT
);
CREATE TABLE IF NOT EXISTS workers (
  id TEXT PRIMARY KEY,
  nama TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  terakhir_terlihat TEXT NOT NULL,
  versi TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  state TEXT NOT NULL DEFAULT 'uploading'
    CHECK (state IN ('uploading','queued','processing','completed',
                     'failed','expired','cancelled','deleted')),
  stage TEXT
    CHECK (stage IS NULL OR stage IN ('probing','transcribing',
                                      'diarizing','merging')),
  nama_berkas_asli TEXT NOT NULL DEFAULT '',
  r2_key TEXT NOT NULL DEFAULT '',
  ukuran_byte INTEGER NOT NULL DEFAULT 0,
  durasi_detik REAL,
  bahasa TEXT NOT NULL DEFAULT 'id',
  diarisasi INTEGER NOT NULL DEFAULT 0 CHECK (diarisasi IN (0, 1)),
  min_pembicara INTEGER
    CHECK (min_pembicara IS NULL OR (min_pembicara BETWEEN 1 AND 8)),
  maks_pembicara INTEGER
    CHECK (maks_pembicara IS NULL OR (maks_pembicara BETWEEN 1 AND 8)),
  menit_dikenakan REAL NOT NULL DEFAULT 0,
  percobaan INTEGER NOT NULL DEFAULT 0,
  worker_id TEXT REFERENCES workers(id) ON DELETE SET NULL,
  lease_sampai TEXT,
  dibuat_pada TEXT NOT NULL,
  selesai_pada TEXT,
  audio_dihapus_pada TEXT,
  hapus_transkrip_pada TEXT,
  kode_galat TEXT,
  versi_model TEXT
);
CREATE TABLE IF NOT EXISTS segments (
  job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  urut INTEGER NOT NULL,
  mulai REAL NOT NULL,
  selesai REAL NOT NULL,
  teks TEXT NOT NULL DEFAULT '',
  keyakinan REAL NOT NULL DEFAULT 0,
  speaker_id TEXT,
  disunting INTEGER NOT NULL DEFAULT 0 CHECK (disunting IN (0, 1)),
  versi INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (job_id, urut)
);
CREATE TABLE IF NOT EXISTS speakers (
  job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  speaker_id TEXT NOT NULL,
  label_asli TEXT NOT NULL,
  nama_tampil TEXT NOT NULL,
  PRIMARY KEY (job_id, speaker_id)
);
CREATE TABLE IF NOT EXISTS usage_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tanggal_lokal TEXT NOT NULL,
  job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
  menit REAL NOT NULL,
  jenis TEXT NOT NULL CHECK (jenis IN ('kenakan', 'kembalikan'))
);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  waktu TEXT NOT NULL,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  jenis TEXT NOT NULL,
  job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_state_dibuat ON jobs(state, dibuat_pada);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);
"""

MIGRATION_001_DOWN = """
DROP INDEX IF EXISTS idx_jobs_user;
DROP INDEX IF EXISTS idx_jobs_state_dibuat;
DROP TABLE IF EXISTS audit_events;
DROP TABLE IF EXISTS usage_ledger;
DROP TABLE IF EXISTS speakers;
DROP TABLE IF EXISTS segments;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS workers;
DROP TABLE IF EXISTS consents;
DROP TABLE IF EXISTS allowlist;
DROP TABLE IF EXISTS users;
"""

MIGRATION_002_UP = """
CREATE TABLE IF NOT EXISTS anon_sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ip_hash TEXT NOT NULL,
  dibuat_pada TEXT NOT NULL,
  terakhir_dilihat TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anon_ip ON anon_sessions(ip_hash);
CREATE INDEX IF NOT EXISTS idx_anon_user ON anon_sessions(user_id);

CREATE TABLE IF NOT EXISTS upload_sessions (
  job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  upload_id TEXT NOT NULL,
  part_size INTEGER NOT NULL,
  part_count INTEGER NOT NULL,
  dibuat_pada TEXT NOT NULL,
  selesai_pada TEXT
);
CREATE INDEX IF NOT EXISTS idx_upload_selesai ON upload_sessions(selesai_pada);

CREATE TABLE IF NOT EXISTS job_metrics (
  job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  xrt REAL,
  low_confidence_ratio REAL,
  worker_seconds REAL,
  model_version TEXT,
  edit_chars INTEGER NOT NULL DEFAULT 0,
  total_chars INTEGER NOT NULL DEFAULT 0,
  dikirim_pada TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kunci TEXT NOT NULL,
  waktu TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_kunci_waktu ON rate_events(kunci, waktu);
"""

MIGRATION_002_DOWN = """
DROP INDEX IF EXISTS idx_rate_kunci_waktu;
DROP TABLE IF EXISTS rate_events;
DROP TABLE IF EXISTS job_metrics;
DROP INDEX IF EXISTS idx_upload_selesai;
DROP TABLE IF EXISTS upload_sessions;
DROP INDEX IF EXISTS idx_anon_user;
DROP INDEX IF EXISTS idx_anon_ip;
DROP TABLE IF EXISTS anon_sessions;
"""

MIGRATIONS: list[tuple[int, str, str]] = [
    (1, MIGRATION_001_UP, MIGRATION_001_DOWN),
    (2, MIGRATION_002_UP, MIGRATION_002_DOWN),
]

LATEST_VERSION = MIGRATIONS[-1][0]
