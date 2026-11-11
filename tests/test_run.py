"""S-KPISEM Hefesto SCRIPT contract: env-only inputs, loud failure, exit codes, idempotent output,
opt-in upload."""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = (
    "demo_view\nСинтетик.\n\nХэмжигдэхүүн (2):\n"
    "· demo_view.a — Идэвхжлийн хувь [нэгж: хэрэглэгч · grain: daily_snapshot · MET-PLAT-0001]"
    " ≈ A, AAA, AAA-001\n"
    "· demo_view.b — Зээлийн өсөлт [нэгж: хувь · grain: daily_snapshot · MET-PLAT-0002] ≈ B, AAA, AAA-002\n"
    "\nХэмжээс (1):\n· demo_view.snapshot_date — огноо\n"
)


def load_run() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s_kpisem_run", ROOT / "agent" / "run.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def run() -> ModuleType:
    return load_run()


def env_with(tmp_path: Path, files: dict[str, str], **extra: str) -> dict[str, str]:
    inbox = tmp_path / "in"
    inbox.mkdir(parents=True)
    for name, text in files.items():
        (inbox / name).write_text(text, encoding="utf-8")
    return {"INPUT_ATTACHMENTS_DIR": str(inbox), "KPISEM_OUT_DIR": str(tmp_path / "out"), **extra}


def test_missing_input_fails_loudly(run: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    assert run.main({}) == run.EXIT_INPUT
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert last.startswith("RESULT: success=false summary=INPUT_ATTACHMENTS_DIR алга")


@pytest.mark.parametrize("files", [{}, {"a.txt": SAMPLE, "b.txt": SAMPLE}])
def test_exactly_one_text_file_is_required(run: ModuleType, tmp_path: Path, files: dict[str, str]) -> None:
    assert run.main(env_with(tmp_path, files)) == run.EXIT_INPUT


def test_text_without_measures_is_refused(run: ModuleType, tmp_path: Path) -> None:
    assert run.main(env_with(tmp_path, {"x.txt": "hello"})) == run.EXIT_INPUT


def test_success_writes_report_and_result_line(
    run: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = env_with(tmp_path, {"describe.txt": SAMPLE}, HEFESTO_ISSUE_KEY="SRVDSK-1")
    assert run.main(env) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1].startswith("RESULT: success=true outcome=DONE summary=demo_view: 2 measure, HIGH 1")
    outputs = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert len(outputs) == 2 and all("SRVDSK-1" in name for name in outputs)
    csv_text = next((tmp_path / "out").glob("*.csv")).read_text(encoding="utf-8-sig")
    assert "RATE_UNIT_MISMATCH" in csv_text and "Шийдвэр" in csv_text

    assert run.main(env) == 0  # re-run for the same issue overwrites, never duplicates
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == outputs


def test_attach_is_off_by_default_and_needs_hefesto_env(
    run: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[Any] = []
    monkeypatch.setattr(run.urllib.request, "urlopen", lambda *a, **k: called.append(a))
    assert run.main(env_with(tmp_path, {"d.txt": SAMPLE})) == 0 and called == []
    assert run.main(env_with(tmp_path / "x", {"d.txt": SAMPLE}, KPISEM_ATTACH="1")) == run.EXIT_UPLOAD


def test_attach_posts_csv_to_the_issue(
    run: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[Any] = []

    class Response:
        status = 201

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request: Any, timeout: int) -> Response:
        sent.append(request)
        return Response()

    monkeypatch.setattr(run.urllib.request, "urlopen", fake_urlopen)
    env = env_with(tmp_path, {"d.txt": SAMPLE}, KPISEM_ATTACH="1", HEFESTO_API="https://hefesto.test/api/",
                   HEFESTO_TOKEN="secret-token", INPUT_ISSUE_ID="3946")  # fmt: skip
    assert run.main(env) == 0
    (request,) = sent
    assert request.full_url == "https://hefesto.test/api/runner/issues/3946/attachments"
    assert request.get_header("X-runner-token") == "secret-token"


def test_token_never_reaches_output(
    run: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken(*args: Any, **kwargs: Any) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(run.urllib.request, "urlopen", broken)
    env = env_with(tmp_path, {"d.txt": SAMPLE}, KPISEM_ATTACH="1", HEFESTO_API="https://h.test",
                   HEFESTO_TOKEN="secret-token", INPUT_ISSUE_ID="1")  # fmt: skip
    assert run.main(env) == run.EXIT_UPLOAD
    captured = capsys.readouterr()
    assert "secret-token" not in captured.out + captured.err


def test_agent_code_uses_only_the_standard_library() -> None:
    # The Hefesto runner has no third-party packages.
    for path in (
        ROOT / "agent" / "run.py",
        ROOT / "agent" / "audit.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots = [node.module.split(".")[0]]
            else:
                continue
            for root in roots:
                assert root in sys.stdlib_module_names or root == "agent", f"{path.name}: {root}"


@pytest.mark.parametrize(("api", "issue"), [("file:///etc/passwd", "1"), ("https://h.test", "1/../../x")])
def test_attach_refuses_non_http_urls_and_odd_issue_ids(
    run: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, api: str, issue: str
) -> None:
    monkeypatch.setattr(run.urllib.request, "urlopen", lambda *a, **k: pytest.fail("must not be called"))
    env = env_with(tmp_path, {"d.txt": SAMPLE}, KPISEM_ATTACH="1", HEFESTO_API=api, HEFESTO_TOKEN="t",
                   INPUT_ISSUE_ID=issue)  # fmt: skip
    assert run.main(env) == run.EXIT_UPLOAD


def test_golden_set_passes_completely() -> None:
    # Rule-based agent: every golden case must pass. The 90% gate is for LLM variance; here a miss is a bug.
    import json
    import subprocess

    result = subprocess.run(
        [sys.executable, str(ROOT / "eval" / "run_eval.py")], capture_output=True, text=True, encoding="utf-8",
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = sorted((ROOT / "eval" / "reports").glob("eval_*.json"))[-1]
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["passed"] == data["total"] >= 30, [c for c in data["cases"] if not c["passed"]]
