from worker import doctor
from worker.bench import cmd_bench
from worker.cli import build_parser


def test_doctor_keys():
    report = doctor.run_doctor(workdir=".")
    for key in ("gpu", "ffmpeg", "torch-cuda", "hf-token",
                "battery", "workdir"):
        assert key in report
        assert report[key]["ok"] in ("true", "false")
    assert report["status"] in ("ok", "fail")


def test_doctor_never_prints_token(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "rahasia-123")
    ok, detail = doctor.check_hf_token()
    assert ok is True
    assert "rahasia" not in detail


def test_bench_empty_folder(tmp_path):
    args = build_parser().parse_args(["bench", str(tmp_path)])
    assert cmd_bench(args) == 1


def test_doctor_report_compat():
    from worker.cli import doctor_report
    assert doctor_report()["status"] == "ok"
