"""TK-005: full laptop environment checks for the BeosaBasi worker host.

Read-only: never prints secrets (HF token presence only), never writes
outside the workdir probe. Each check returns ok + detail; the CLI prints
a pass/fail report and exits nonzero when anything fails.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tempfile

NVIDIA_SMI = shutil.which("nvidia-smi")  # resolved at import; tests monkeypatch


def _run(cmd: list[str], timeout: int = 15) -> tuple[bool, str]:
    try:
        out = subprocess.run(cmd, check=False,
                             capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    text = (out.stdout or "") + (out.stderr or "")
    return out.returncode == 0, text.strip()


def check_gpu() -> tuple[bool, str]:
    ok, text = _run(["nvidia-smi",
                     ("--query-gpu=name,memory.total,memory.free,"
                      "driver_version,temperature.gpu"),
                     "--format=csv,noheader"])
    if not ok or not text:
        return False, "nvidia-smi tidak ada / gagal (pasang driver NVIDIA)"
    parts = [p.strip() for p in text.splitlines()[0].split(",")]
    if len(parts) < 5:
        return False, f"keluaran nvidia-smi tak dikenal: {text[:120]}"
    name, _total, free = parts[0], parts[1], parts[2]
    try:
        free_mib = float(free.split()[0])
    except ValueError:
        free_mib = 0.0
    if free_mib < 5500:
        return False, f"{name}: VRAM bebas {free} (< 5500 MiB, tutup app berat)"
    return True, f"{name} driver={parts[3]} bebas={free} suhu={parts[4]}C"


def check_ffmpeg() -> tuple[bool, str]:
    details = []
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            return False, f"{tool} tidak ditemukan di PATH"
        _ok, text = _run([tool, "-version"])
        first = text.splitlines()[0] if text else "?"
        m = re.search(r"version (\S+)", first)
        details.append(f"{tool} {m.group(1) if m else '?'}")
    return True, ", ".join(details)


def check_torch_cuda() -> tuple[bool, str]:
    import importlib.util

    if importlib.util.find_spec("torch") is None:
        return False, "torch belum dipasang (lihat requirements.lock)"
    import torch

    if not torch.cuda.is_available():
        return False, f"torch {torch.__version__} ada tapi CUDA tak terlihat"
    ct2 = ("ctranslate2 " + __import__("ctranslate2").__version__
           if importlib.util.find_spec("ctranslate2") else "ctranslate2 hilang")
    fw = ("faster-whisper ok"
          if importlib.util.find_spec("faster_whisper") else "faster-whisper hilang")
    name = torch.cuda.get_device_name(0)
    return True, f"torch {torch.__version__} + {name} | {ct2} | {fw}"


def check_workdir(path: str) -> tuple[bool, str]:
    try:
        os.makedirs(path, exist_ok=True)
        fd, probe = tempfile.mkstemp(dir=path, prefix=".writetest-")
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        return False, f"{path} tak bisa ditulis: {exc}"
    return True, f"{path} bisa ditulis"


def check_hf_token() -> tuple[bool, str]:
    for var in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
        if os.environ.get(var):
            return True, f"{var} ada (isi tidak ditampilkan)"
    return False, "token Hugging Face belum ada (set HF_TOKEN di env, untuk TK-050)"


def check_battery() -> tuple[bool, str]:
    """Non-fatal info: worker refuses jobs <30% on battery in TK-034."""
    if platform.system() != "Windows":
        return True, "bukan Windows, cek baterai dilewati"
    try:
        import ctypes

        class PS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_byte),
                        ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte),
                        ("Reserved1", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong),
                        ("BatteryFullLifeTime", ctypes.c_ulong)]

        ps = PS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(ps)):
            return True, "status daya tak terbaca (info saja)"
        pct = int(ps.BatteryLifePercent)
        if pct > 100:  # 255 = unknown/no battery
            return True, "tanpa baterai / tak terbaca (desktop mode)"
        on_batt = ps.ACLineStatus == 0
        return True, f"baterai {pct}% ({'baterai' if on_batt else 'colok listrik'})"
    except Exception as exc:  # noqa: BLE001 - info only, never fail doctor
        return True, f"cek baterai dilewati: {exc}"


CHECKS = [
    ("gpu", check_gpu),
    ("ffmpeg", check_ffmpeg),
    ("torch-cuda", check_torch_cuda),
    ("hf-token", check_hf_token),
    ("battery", check_battery),
]


def run_doctor(workdir: str = ".") -> dict[str, dict[str, str]]:
    report: dict[str, dict[str, str]] = {
        "python": {"ok": "true", "detail": platform.python_version()},
        "platform": {"ok": "true", "detail": platform.platform()},
    }
    for name, fn in CHECKS:
        ok, detail = fn()
        report[name] = {"ok": "true" if ok else "false", "detail": detail}
    ok, detail = check_workdir(workdir)
    report["workdir"] = {"ok": "true" if ok else "false", "detail": detail}
    report["status"] = "ok" if all(
        v["ok"] == "true" for k, v in report.items() if k != "status") else "fail"
    return report
