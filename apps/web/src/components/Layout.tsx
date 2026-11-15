// Kerangka aplikasi: sidebar, topbar, latar bukit biru, toast, palette,
// modal persetujuan — plus penyedia data bersama (polling API).

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { Agentation } from "agentation";
import { BarChart3, CheckCircle2, Copy, Download, FileUp, Library, Moon, ShieldCheck, Sparkles } from "lucide-react";
import { api, ApiError } from "../api/client";
import { PESAN_GALAT } from "../api/errors";
import type { JobSummary, Me, ProcessingStage } from "../api-types";
import {
  uiJobCard,
  uiTranscript,
} from "../lib/adapters";
import { buildTXT, fileBase, downloadText, initialsOf } from "../lib/ui";
import { modKey } from "../lib/platform";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import CommandPalette from "./CommandPalette";
import PrivacyConsent from "./PrivacyConsent";
import {
  CONSENT_VERSION,
  DAILY_MINUTES,
  IDLE_UPLOAD,
  MAX_ACTIVE,
  StudioContext,
  type PendingUpload,
  type Studio,
  type UiJobLite,
  type UploadFileMeta,
} from "./studio";

const JOBS_POLL_MS = 8000;
const HEALTH_POLL_MS = 30000;
const JOB_POLL_MS = 3000;

const STAGE_PROGRESS: Record<ProcessingStage, number> = {
  probing: 14,
  transcribing: 52,
  diarizing: 78,
  merging: 94,
};

function prettyName(email: string): string {
  const local = email.split("@")[0] ?? "pengguna";
  return local
    .split(/[._-]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatWib(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("id-ID", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function Layout(): React.JSX.Element {
  const navigate = useNavigate();
  const location = useLocation();

  const [theme, setTheme] = useState<"dark" | "light">(() => {
    const saved = localStorage.getItem("ow-theme");
    return saved === "light" ? "light" : "dark";
  });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [workerOnline, setWorkerOnline] = useState(true);
  const [upload, setUpload] = useState(IDLE_UPLOAD);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState("");
  const [toastOpen, setToastOpen] = useState(false);
  const [consentOpen, setConsentOpen] = useState(false);
  const [consentReadOnly, setConsentReadOnly] = useState(true);
  const [pending, setPending] = useState<PendingUpload | null>(null);

  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const uploadAbort = useRef(false);
  const consentRef = useRef(false);

  useEffect(() => {
    consentRef.current = (me?.consent ?? null) !== null;
  }, [me]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("ow-theme", theme);
  }, [theme]);

  const toast = useCallback((message: string) => {
    setToastMsg(message);
    setToastOpen(true);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastOpen(false), 3200);
  }, []);

  const refreshHealth = useCallback(() => {
    api
      .getHealth()
      .then((h) => setWorkerOnline(h.status === "ok"))
      .catch(() => setWorkerOnline(false));
  }, []);

  const refreshJobs = useCallback(() => {
    api
      .listJobs()
      .then((res) => setJobs(res.jobs))
      .catch(() => undefined);
  }, []);

  const refreshMe = useCallback(() => {
    api
      .getMe()
      .then(setMe)
      .catch(() => undefined);
  }, []);

  const refreshData = useCallback(() => {
    refreshMe();
    refreshJobs();
    refreshHealth();
  }, [refreshHealth, refreshJobs, refreshMe]);

  useEffect(() => {
    refreshData();
    const jobsId = setInterval(refreshJobs, JOBS_POLL_MS);
    const healthId = setInterval(refreshHealth, HEALTH_POLL_MS);
    return () => {
      clearInterval(jobsId);
      clearInterval(healthId);
    };
  }, [refreshData, refreshHealth, refreshJobs]);

  // ---- unggahan: kontrak multipart nyata -------------------------------

  const startUpload = useCallback(
    (file: File, meta: UploadFileMeta) => {
      if (me !== null && !consentRef.current) {
        setPending({ file, meta });
        setConsentReadOnly(false);
        setConsentOpen(true);
        return;
      }
      void (async () => {
        uploadAbort.current = false;
        setUpload({
          phase: "uploading",
          progress: 0,
          fileMeta: meta,
          stage: null,
          jobId: null,
          error: null,
        });
        const contentType = file.type || "application/octet-stream";
        try {
          const session = await api.initUpload({
            filename: file.name,
            size_bytes: file.size,
            content_type: contentType,
            language: meta.language,
            diarization: meta.diarized,
            min_speakers: meta.diarized ? meta.speakers : undefined,
            max_speakers: meta.diarized ? meta.speakers : undefined,
            turnstile_token: "stub",
          });
          const parts: { part_number: number; etag: string }[] = [];
          for (let i = 0; i < session.part_count; i += 1) {
            if (uploadAbort.current) {
              setUpload(IDLE_UPLOAD);
              return;
            }
            const sign = await api.signPart(session.upload_id, { part_number: i });
            const blob = file.slice(
              i * session.part_size,
              Math.min(file.size, (i + 1) * session.part_size),
            );
            const etag = await new Promise<string>((resolve, reject) => {
              const xhr = new XMLHttpRequest();
              xhr.open("PUT", sign.url);
              xhr.upload.onprogress = (e) => {
                if (!e.lengthComputable) return;
                const overall = ((i + e.loaded / e.total) / session.part_count) * 95;
                setUpload((prev) => (prev.phase === "uploading" ? { ...prev, progress: overall } : prev));
              };
              xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                  resolve(xhr.getResponseHeader("ETag") ?? xhr.getResponseHeader("etag") ?? "");
                } else {
                  reject(new ApiError(xhr.status, PESAN_GALAT.INTERNAL));
                }
              };
              xhr.onerror = () => reject(new ApiError(0, PESAN_GALAT.INTERNAL));
              xhr.send(blob);
            });
            parts.push({ part_number: i, etag });
          }
          if (uploadAbort.current) {
            setUpload(IDLE_UPLOAD);
            return;
          }
          const job = await api.completeUpload(session.upload_id, { parts });
          setUpload((prev) => ({ ...prev, phase: "queued", progress: 100, jobId: job.job_id }));
          refreshJobs();
          refreshMe();
          toast("Berkas masuk antrean transkripsi");
        } catch (error) {
          const message =
            error instanceof ApiError ? error.message : PESAN_GALAT.INTERNAL;
          setUpload({ ...IDLE_UPLOAD, phase: "failed", error: message, fileMeta: meta });
          toast(`Unggahan gagal — ${message}`);
        }
      })();
    },
    [me, refreshJobs, refreshMe, toast],
  );

  const cancelUpload = useCallback(
    (force = false) => {
      uploadAbort.current = true;
      if (!force && upload.phase === "queued") toast("Job antre tetap diproses; unggahan baru menunggu");
      else toast(force ? "Siap untuk unggahan baru" : "Unggahan dibatalkan");
      setUpload(IDLE_UPLOAD);
    },
    [toast, upload.phase],
  );

  // pantau job yang sedang diunggah sampai selesai
  useEffect(() => {
    if (upload.jobId === null) return;
    if (!["queued", "processing"].includes(upload.phase)) return;
    let aktif = true;
    const tick = setInterval(() => {
      void (async () => {
        try {
          const detail = await api.getJob(upload.jobId as string);
          if (!aktif) return;
          const state = detail.job.state;
          if (state === "processing") {
            const stage = detail.job.stage ?? "transcribing";
            setUpload((prev) => ({
              ...prev,
              phase: "processing",
              stage,
              progress: STAGE_PROGRESS[stage] ?? prev.progress,
            }));
          } else if (state === "completed") {
            setUpload((prev) => ({ ...prev, phase: "completed", progress: 100, stage: null }));
            clearInterval(tick);
          } else if (state === "failed" || state === "expired") {
            const code = detail.job.error_code;
            setUpload((prev) => ({
              ...prev,
              phase: "failed",
              stage: null,
              error: code ? PESAN_GALAT[code] : PESAN_GALAT.INTERNAL,
            }));
            clearInterval(tick);
          }
          refreshJobs();
        } catch {
          // biarkan polling berikutnya mencoba lagi
        }
      })();
    }, JOB_POLL_MS);
    return () => {
      aktif = false;
      clearInterval(tick);
    };
  }, [refreshJobs, upload.jobId, upload.phase]);

  // ---- persetujuan ------------------------------------------------------

  const consentGiven = (me?.consent ?? null) !== null;

  const openNotice = useCallback((options?: { pending?: PendingUpload | null }) => {
    setPending(options?.pending ?? null);
    setConsentReadOnly(options?.pending === undefined || options?.pending === null);
    setConsentOpen(true);
  }, []);

  const openGrant = useCallback(() => {
    setPending(null);
    setConsentReadOnly(false);
    setConsentOpen(true);
  }, []);

  const onAgreeConsent = useCallback(() => {
    void (async () => {
      try {
        await api.giveConsent({ document_version: CONSENT_VERSION, age_confirmed: true });
        consentRef.current = true;
        refreshMe();
        setConsentOpen(false);
        const queued = pending;
        setPending(null);
        if (queued) startUpload(queued.file, queued.meta);
        else toast("Persetujuan privasi dicatat");
      } catch (error) {
        toast(error instanceof ApiError ? error.message : PESAN_GALAT.INTERNAL);
      }
    })();
  }, [pending, refreshMe, startUpload, toast]);

  const onWithdrawConsent = useCallback(() => {
    void (async () => {
      try {
        await api.withdrawConsent();
        refreshMe();
        toast("Persetujuan ditarik — unggahan berikutnya akan meminta persetujuan ulang");
      } catch (error) {
        toast(error instanceof ApiError ? error.message : PESAN_GALAT.INTERNAL);
      }
    })();
  }, [refreshMe, toast]);

  // ---- navigasi & pencarian ---------------------------------------------

  const uiJobs = useMemo(() => jobs.map(uiJobCard), [jobs]);

  const searchResults = useMemo<UiJobLite[]>(() => {
    const q = query.trim().toLowerCase();
    if (q === "") return [];
    return uiJobs
      .filter((job) =>
        `${job.title} ${job.file} ${job.language} ${job.format}`
          .toLowerCase()
          .includes(q),
      )
      .slice(0, 5)
      .map((job) => ({
        id: job.id,
        title: job.title,
        file: job.file,
        format: job.format,
        duration: job.duration,
        status: job.status,
      }));
  }, [query, uiJobs]);

  const navigateView = useCallback(
    (view: "home" | "library" | "insights" | "settings") => {
      const targets = { home: "/", library: "/jobs", insights: "/insights", settings: "/settings" };
      navigate(targets[view]);
      setSidebarOpen(false);
      setPaletteOpen(false);
      window.scrollTo({ top: 0, behavior: "auto" });
    },
    [navigate],
  );

  const goJob = useCallback(
    (id: string) => {
      navigate(`/jobs/${id}`);
      setPaletteOpen(false);
      window.scrollTo({ top: 0, behavior: "auto" });
    },
    [navigate],
  );

  const selectJob = useCallback(
    (id: string, title: string) => {
      setActiveId(id);
      setSidebarOpen(false);
      setQuery("");
      setPaletteOpen(false);
      navigate("/");
      window.scrollTo({ top: 0, behavior: "auto" });
      toast(`Membuka “${title}”`);
    },
    [navigate, toast],
  );

  const startNew = useCallback(() => {
    navigateView("home");
    toast("Pilih berkas audio untuk diunggah");
    setTimeout(() => {
      document.querySelector(".upload-panel")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
  }, [navigateView, toast]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(target?.tagName ?? "");
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((open) => !open);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "u") {
        e.preventDefault();
        startNew();
        return;
      }
      if (e.key === "Escape" && !typing) {
        setPaletteOpen(false);
        setSidebarOpen(false);
        setQuery("");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [startNew]);

  // ---- turunan untuk UI --------------------------------------------------

  const view = useMemo(() => {
    if (location.pathname.startsWith("/jobs/")) return "library";
    if (location.pathname.startsWith("/jobs")) return "library";
    if (location.pathname.startsWith("/insights")) return "insights";
    if (location.pathname.startsWith("/settings")) return "settings";
    return "home";
  }, [location.pathname]);

  const profile = useMemo(() => {
    const email = me?.email ?? "pilot@beosabasi.id";
    return {
      name: prettyName(email),
      email,
      initials: initialsOf(email),
      pilot: "Pilot undangan",
    };
  }, [me]);

  const quota = useMemo(() => {
    const remaining = me?.quota_minutes_remaining ?? DAILY_MINUTES;
    const active = me?.active_jobs ?? 0;
    return {
      minutes: DAILY_MINUTES,
      used: Math.max(0, DAILY_MINUTES - remaining),
      maxActive: MAX_ACTIVE,
      active,
      reset: "00.00 WIB",
    };
  }, [me]);

  const consent = useMemo(() => {
    const c = me?.consent;
    if (!c) return null;
    return {
      version: `v${c.document_version}`,
      given: formatWib(c.given_at),
    };
  }, [me]);

  const featured = useMemo(
    () => uiJobs.find((job) => job.status === "completed") ?? uiJobs[0],
    [uiJobs],
  );

  const paletteActions = useMemo(() => {
    const copyTranscript = (download: boolean) => {
      if (!featured || featured.status !== "completed") {
        toast(
          download
            ? "Pilih job yang sudah selesai untuk mengunduh"
            : "Pilih job yang sudah selesai untuk menyalin transkrip",
        );
        return;
      }
      void (async () => {
        try {
          const res = await api.getTranscript(featured.id);
          const raw = jobs.find((j) => j.job_id === featured.id);
          if (!raw) return;
          const job = uiJobCard(raw);
          const text = buildTXT(job, uiTranscript(res).segments);
          if (download) {
            downloadText(`${fileBase(job)}.txt`, text);
            toast("Transkrip TXT diunduh");
          } else {
            await navigator.clipboard.writeText(text);
            toast("Transkrip disalin ke clipboard");
          }
        } catch {
          toast(download ? "Unduhan gagal. Coba lagi." : "Clipboard tidak tersedia");
        }
      })();
    };

    return [
      {
        label: "Unggah berkas audio",
        desc: "MP3, M4A, WAV, FLAC, OGG, OPUS, MP4, WEBM · maks 200 MB",
        hint: `${modKey}U`,
        icon: FileUp,
        run: startNew,
      },
      {
        label: "Buka pustaka",
        desc: "Semua job, status antrean, dan transkrip",
        hint: "G P",
        icon: Library,
        run: () => navigateView("library"),
      },
      {
        label: "Buka pemakaian",
        desc: "Kuota harian, status job, dan retensi",
        hint: "G W",
        icon: BarChart3,
        run: () => navigateView("insights"),
      },
      {
        label: theme === "dark" ? "Ganti ke tema terang" : "Ganti ke tema gelap",
        desc: "Sesuaikan tampilan ruang kerja",
        icon: theme === "dark" ? Moon : Sparkles,
        run: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
      },
      {
        label: "Buka pemberitahuan privasi",
        desc: `Versi v${CONSENT_VERSION} · retensi audio 24 jam`,
        icon: ShieldCheck,
        run: () => openNotice(),
      },
      {
        label: "Salin transkrip aktif",
        desc: featured ? featured.title : "Belum ada job",
        icon: Copy,
        run: () => copyTranscript(false),
      },
      {
        label: "Unduh transkrip aktif (TXT)",
        desc: featured ? featured.file : "Belum ada job",
        icon: Download,
        run: () => copyTranscript(true),
      },
    ];
  }, [featured, jobs, navigateView, openNotice, startNew, theme, toast]);

  const ctx: Studio = {
    theme,
    toggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    view,
    navigate: navigateView,
    goJob,
    me,
    profile,
    quota,
    consent,
    consentGiven,
    jobs,
    refreshData,
    workerOnline,
    refreshHealth,
    upload,
    startUpload,
    cancelUpload,
    query,
    setQuery,
    searchResults,
    activeId,
    selectJob,
    toast,
    openNotice,
    openGrant,
    onAgreeConsent,
    onWithdrawConsent,
  };

  return (
    <StudioContext.Provider value={ctx}>
      <div className="app">
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onNew={startNew}
        />

        <div className="main">
          <div className="main-scene" aria-hidden="true">
            <div className="scene-sun-wrap">
              <svg className="scene-sun" viewBox="0 0 900 900" fill="none" focusable="false">
                <circle cx="450" cy="450" r="420" fill="var(--scene-sun-fill)" />
                <circle cx="450" cy="450" r="420" stroke="var(--scene-sun)" strokeWidth="1.4" />
                <circle
                  cx="450"
                  cy="450"
                  r="300"
                  stroke="var(--scene-sun)"
                  strokeWidth="1.2"
                  opacity="0.7"
                />
                <circle
                  cx="450"
                  cy="450"
                  r="180"
                  stroke="var(--scene-sun)"
                  strokeWidth="1"
                  opacity="0.5"
                />
              </svg>
            </div>

            <svg
              className="scene-hills"
              viewBox="0 0 1600 500"
              preserveAspectRatio="none"
              focusable="false"
            >
              <defs>
                <pattern id="sceneGrain" width="7" height="7" patternUnits="userSpaceOnUse">
                  <circle cx="1.6" cy="1.6" r="1.3" fill="var(--scene-grain)" />
                </pattern>
              </defs>
              <g className="scene-hill is-far">
                <path
                  d="M-160 500C-130 310 20 170 250 185C450 198 600 350 660 500Z"
                  fill="var(--scene-hill-back)"
                />
              </g>
              <g className="scene-hill is-far">
                <path
                  d="M880 500C950 280 1130 120 1350 150C1540 176 1680 340 1740 500Z"
                  fill="var(--scene-hill-back)"
                />
              </g>
              <g className="scene-hill is-far">
                <path
                  d="M120 500C200 360 330 300 470 320C600 340 700 420 740 500Z"
                  fill="var(--scene-hill-back)"
                />
              </g>
              <g className="scene-hill is-mid">
                <path
                  d="M380 500C450 380 590 320 750 342C920 365 1040 440 1090 500Z"
                  fill="var(--scene-hill-mid)"
                />
              </g>
              <g className="scene-hill is-near">
                <path
                  d="M-120 500C-20 440 150 410 330 430C520 452 680 480 760 500Z"
                  fill="var(--scene-hill-mid)"
                />
              </g>
              <g className="scene-hill is-near">
                <path
                  d="M980 500C1080 450 1230 430 1380 448C1500 462 1580 482 1640 500Z"
                  fill="var(--scene-hill-mid)"
                />
              </g>
              <g className="scene-grain">
                <path
                  d="M-160 500C-130 310 20 170 250 185C450 198 600 350 660 500Z"
                  fill="url(#sceneGrain)"
                />
                <path
                  d="M880 500C950 280 1130 120 1350 150C1540 176 1680 340 1740 500Z"
                  fill="url(#sceneGrain)"
                />
                <path
                  d="M120 500C200 360 330 300 470 320C600 340 700 420 740 500Z"
                  fill="url(#sceneGrain)"
                />
                <path
                  d="M380 500C450 380 590 320 750 342C920 365 1040 440 1090 500Z"
                  fill="url(#sceneGrain)"
                />
                <path
                  d="M-120 500C-20 440 150 410 330 430C520 452 680 480 760 500Z"
                  fill="url(#sceneGrain)"
                />
                <path
                  d="M980 500C1080 450 1230 430 1380 448C1500 462 1580 482 1640 500Z"
                  fill="url(#sceneGrain)"
                />
              </g>
            </svg>

            {SCENE_BIRDS.map((bird) => (
              <span
                key={`${bird.top}-${bird.right}`}
                className="scene-bird"
                style={
                  {
                    top: bird.top,
                    right: bird.right,
                    width: bird.width,
                    "--bird-rot": `${bird.rotate}deg`,
                    "--bird-delay": `${bird.delay}s`,
                  } as CSSProperties
                }
              />
            ))}

            <svg className="scene-flower-defs" width="0" height="0" focusable="false">
              <defs>
                <symbol id="sceneFlower" viewBox="0 0 40 64">
                  <path
                    d="M20 62V26"
                    stroke="var(--scene-stem)"
                    strokeWidth="1.4"
                    strokeLinecap="round"
                  />
                  <path d="M20 45c-8-1-12-6-13-11 7 0 12 4 13 11Z" fill="var(--scene-leaf)" />
                  <path d="M20 52c6-1 10-5 11-9-6 0-10 3-11 9Z" fill="var(--scene-leaf)" />
                  <g fill="var(--scene-petal)">
                    <circle cx="20" cy="15" r="5.2" />
                    <circle cx="28.5" cy="21" r="5.2" />
                    <circle cx="25.2" cy="31" r="5.2" />
                    <circle cx="14.8" cy="31" r="5.2" />
                    <circle cx="11.5" cy="21" r="5.2" />
                  </g>
                  <circle cx="20" cy="24" r="2.6" fill="var(--scene-flower-core)" />
                </symbol>
              </defs>
            </svg>

            {SCENE_FLOWERS.map((flower) => (
              <svg
                key={`${flower.left ?? flower.right}-${flower.bottom}`}
                className={`scene-flower ${flower.corner ? "is-corner" : ""}`}
                viewBox="0 0 40 64"
                focusable="false"
                style={
                  {
                    left: flower.left,
                    right: flower.right,
                    bottom: flower.bottom,
                    width: flower.size,
                    "--flower-rot": `${flower.rotate}deg`,
                  } as CSSProperties
                }
              >
                <use href="#sceneFlower" />
              </svg>
            ))}
          </div>

          <Topbar
            view={view}
            workerOnline={workerOnline}
            onPalette={() => setPaletteOpen(true)}
            onMenu={() => setSidebarOpen(true)}
          />

          <main className="content">
            <Outlet context={ctx} />
          </main>
        </div>

        <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} actions={paletteActions} />

        <PrivacyConsent
          open={consentOpen}
          pending={pending?.meta ?? null}
          readOnly={consentReadOnly}
          consent={consent}
          onAgree={onAgreeConsent}
          onClose={() => {
            setConsentOpen(false);
            if (pending) toast("Unggahan dibatalkan sebelum dimulai");
            setPending(null);
          }}
        />

        <div className={`toast ${toastOpen ? "is-visible" : ""}`} role="status" aria-live="polite">
          <span className="toast-icon">
            <CheckCircle2 size={16} />
          </span>
          <span>{toastMsg}</span>
        </div>

        {import.meta.env.DEV ? <Agentation appName="Beosabasi" /> : null}
      </div>
    </StudioContext.Provider>
  );
}

const SCENE_BIRDS = [
  { top: "8vh", right: "8%", width: 44, rotate: -8, delay: 0 },
  { top: "15vh", right: "15%", width: 30, rotate: 6, delay: 1.1 },
  { top: "6vh", right: "22%", width: 24, rotate: -4, delay: 2.2 },
  { top: "22vh", right: "3.5%", width: 36, rotate: 10, delay: 0.6 },
];

const SCENE_FLOWERS = [
  { left: "1.6%", bottom: "4vh", size: 28, rotate: -6, corner: true },
  { left: "4.2%", bottom: "10vh", size: 19, rotate: 7 },
  { left: "7.2%", bottom: "17vh", size: 24, rotate: -3 },
  { right: "1.6%", bottom: "5vh", size: 30, rotate: 5, corner: true },
  { right: "4.6%", bottom: "11vh", size: 20, rotate: -8 },
  { right: "7.8%", bottom: "18vh", size: 25, rotate: 4 },
  { left: "30%", bottom: "2.2vh", size: 16, rotate: 8 },
  { left: "68%", bottom: "2.6vh", size: 18, rotate: -5 },
];
