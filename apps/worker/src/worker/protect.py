"""TK-034 laptop protection (PRD AI-08).

No new job below battery threshold unless plugged in; warn on hot GPU;
hold Windows awake during a job and release on idle. All probes are
injectable so tests never touch hardware.
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def read_battery() -> tuple[int | None, bool]:
    """Return (percent, plugged_in). (None, True) when unreadable."""
    if sys.platform != "win32":
        return None, True
    try:
        import ctypes as _ct

        class PowerStatus(_ct.Structure):
            _fields_ = [("ACLineStatus", _ct.c_byte),
                        ("BatteryFlag", _ct.c_byte),
                        ("BatteryLifePercent", _ct.c_byte),
                        ("Reserved1", _ct.c_byte),
                        ("BatteryLifeTime", _ct.c_ulong),
                        ("BatteryFullLifeTime", _ct.c_ulong)]

        st = PowerStatus()
        if not _ct.windll.kernel32.GetSystemPowerStatus(_ct.byref(st)):
            return None, True
        return int(st.BatteryLifePercent), st.ACLineStatus == 1
    except OSError:
        return None, True


def read_gpu_temp() -> int | None:
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu",
             "--format=csv,noheader,nounits"],
            check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    try:
        return int(float(out.stdout.strip().splitlines()[0]))
    except (IndexError, ValueError):
        return None


@contextmanager
def hold_awake() -> Iterator[None]:
    """Prevent Windows sleep inside the block; no-op elsewhere."""
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        except OSError:
            yield
            return
        try:
            yield
        finally:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            except OSError:
                pass
    else:
        yield


def may_take_job(min_battery: int = 30, max_temp: int = 85,
                 battery: Callable[[], tuple[int | None, bool]] = read_battery,
                 gpu_temp: Callable[[], int | None] = read_gpu_temp
                 ) -> tuple[bool, str]:
    percent, plugged = battery()
    if percent is not None and not plugged and percent < min_battery:
        return False, (f"baterai {percent}% (< {min_battery}%) dan tidak dicas "
                       "— colok listrik dulu.")
    temp = gpu_temp()
    if temp is not None and temp > max_temp:
        return False, f"GPU {temp}C melebihi {max_temp}C — dinginkan dulu."
    return True, "ok"
