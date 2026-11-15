# ADR 0001: Identitas anonim tanpa login

- Status: accepted
- Date: 2026-11-15
- Deciders: pemilik produk + agen backend
- Context: Keputusan produk memotong ruang lingkup login Google/OIDC
  (`TK-021`, `TK-022`, `TK-041`). API tetap harus mengaitkan job dengan
  pemiliknya, menegakkan kuota harian 60 menit per pengguna (US-07), dan
  mencegah satu orang memakai kuota berkali-kali hanya dengan menghapus cookie.
  Data pribadi diminimalkan (UU PDP): tidak ada email, nama, atau akun.
- Decision:
  1. Identitas = token acak 256-bit di cookie `beosabasi_session`
     (`HttpOnly`, `SameSite=Lax`, `Secure` di produksi). Server hanya menyimpan
     hash SHA-256 token (`anon_sessions.token_hash`) dan baris `users` sintetis
     (`<uuid>@tanpa-login.invalid`). Tidak ada endpoint login.
  2. Kuota harian dikunci ke hash IP bersalt (`anon_sessions.ip_hash`,
     `BEOSABASI_IP_HASH_SALT`), dihitung dari `usage_ledger` per tanggal UTC+7.
     IP mentah tidak pernah disimpan atau dicatat di log.
  3. Semua endpoint pengguna tetap memakai `cookieAuth` di kontrak; `GET
     /api/me` membuat sesi baru bila cookie belum ada dan tidak pernah 401.
  4. Di belakang Cloudflare/Caddy, `BEOSABASI_TRUST_PROXY=1` membuat API
     membaca `CF-Connecting-IP`/`X-Forwarded-For` untuk hash IP.
- Consequences:
  - Menghapus cookie berarti kehilangan akses ke job lama; tidak ada pemulihan.
    Ini konsisten dengan janji "tanpa akun" dan retensi transkrip 30 hari.
  - Beberapa peramban di IP yang sama (NAT kantor/kampus) berbagi kuota harian.
    Job tetap terpisah per cookie.
  - Token cookie adalah satu-satunya kunci; bila bocor, job dapat dibaca.
    Mitigasi: HTTPS saja, TTL 90 hari, tanpa third-party script di halaman app.
  - Tidak ada consent/allowlist: pilot tertutup mengandalkan Turnstile + kuota
    IP + tautan yang tidak dipublikasikan. Bila pilot dibuka, ADR ini harus
    ditinjau bersama `TK-060`.
