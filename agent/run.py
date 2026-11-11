"""S-KPISEM (KPI Semantic Layer Specialist) v0 — Hefesto SCRIPT-mode entry point.

Contract (Hefesto agent guide, SCRIPT mode): inputs only from env; exit 0 = success, non-zero = failure;
stdout = the report. Python standard library only (no third-party packages on the runner).

Env:
  INPUT_ATTACHMENTS_DIR  required — holds ONE saved `cube_describe_view("indicators_view")` text (.txt)
  HEFESTO_ISSUE_KEY      optional — names the output files (SRVDSK-1234); re-runs overwrite, never duplicate
  KPISEM_OUT_DIR         optional — where the report files go (default: ./out)
  KPISEM_ATTACH=1        optional switch — also attach the review CSV to the issue
                         (needs HEFESTO_API, HEFESTO_TOKEN, INPUT_ISSUE_ID). Off by default.

Read-only towards Cube: nothing in the semantic layer is changed (decision level 1).
"""

import io
import os
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import date
from pathlib import Path

# Repo root on the path so `agent.audit` imports when Hefesto runs `python3 agent/run.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.audit import audit, to_csv, to_markdown  # noqa: E402

EXIT_INPUT = 2  # missing / wrong input: the requester must fix it
EXIT_UPLOAD = 3


def result(success: bool, summary: str, outcome: str = "DONE") -> str:
    head = f"RESULT: success={'true' if success else 'false'}"
    return f"{head} outcome={outcome} summary={summary}" if success else f"{head} summary={summary}"


def fail(code: int, message: str) -> int:
    print(message, file=sys.stderr)
    print(result(False, message))
    return code


def find_input(env: dict[str, str]) -> Path | str:
    folder = env.get("INPUT_ATTACHMENTS_DIR", "").strip()
    if not folder:
        return "INPUT_ATTACHMENTS_DIR алга: cube_describe_view-ийн текст файлыг хүсэлтэд хавсаргана уу"
    candidates = sorted(Path(folder).glob("*.txt"))
    if len(candidates) != 1:
        return f"Хавсралтад яг 1 .txt файл байх ёстой, {len(candidates)} олдлоо"
    return candidates[0]


def attach(env: dict[str, str], path: Path) -> None:
    api, token, issue = env.get("HEFESTO_API"), env.get("HEFESTO_TOKEN"), env.get("INPUT_ISSUE_ID")
    if not (api and token and issue):
        raise RuntimeError("KPISEM_ATTACH=1 боловч HEFESTO_API / HEFESTO_TOKEN / INPUT_ISSUE_ID дутуу")
    if urllib.parse.urlsplit(api).scheme not in ("https", "http") or not issue.isdigit():
        raise RuntimeError(
            "HEFESTO_API нь http(s) хаяг, INPUT_ISSUE_ID нь тоо байх ёстой"
        )  # no file:, no path tricks
    boundary = uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            "Content-Type: text/csv\r\n\r\n"
        ).encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        f"{api.rstrip('/')}/runner/issues/{issue}/attachments",
        data=body,
        method="POST",
        headers={"X-Runner-Token": token, "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - Hefesto API from env
        if response.status >= 300:
            raise RuntimeError(f"attachment upload HTTP {response.status}")


def utf8_output() -> None:
    # The runner's locale may be C/ASCII (or cp1252 on Windows): Mongolian text would crash the report.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(env: dict[str, str] | None = None) -> int:
    utf8_output()
    env = dict(os.environ) if env is None else env
    found = find_input(env)
    if isinstance(found, str):
        return fail(EXIT_INPUT, found)

    report = audit(found.read_text(encoding="utf-8-sig"))
    if not report.measures:
        return fail(EXIT_INPUT, f"{found.name}: measure олдсонгүй — cube_describe_view-ийн гаралт мөн үү?")

    snapshot = date.today().isoformat()
    key = env.get("HEFESTO_ISSUE_KEY") or "manual"
    out = Path(env.get("KPISEM_OUT_DIR") or "out")
    out.mkdir(parents=True, exist_ok=True)
    stem = f"kpi_semantic_audit_{report.view}_{snapshot}_{key}"  # same issue → same names: re-runs overwrite
    markdown = to_markdown(report, snapshot)
    (out / f"{stem}.md").write_text(markdown, encoding="utf-8")
    csv_path = out / f"{stem}.csv"
    csv_path.write_text(to_csv(report, snapshot), encoding="utf-8-sig")  # BOM: Excel/Sheets read UTF-8

    if env.get("KPISEM_ATTACH") == "1":
        try:
            attach(env, csv_path)
        except Exception as exc:  # report the cause, never the token
            return fail(EXIT_UPLOAD, f"Хавсралт илгээж чадсангүй: {type(exc).__name__}: {exc}")

    print(markdown)
    counts = {s: sum(f.severity == s for f in report.findings) for s in ("HIGH", "MEDIUM", "LOW")}
    note = f"; уншиж чадаагүй мөр {len(report.unparsed)}" if report.unparsed else ""
    print(result(True, f"{report.view}: {len(report.measures)} measure, HIGH {counts['HIGH']}, "
                       f"MEDIUM {counts['MEDIUM']}, LOW {counts['LOW']}{note}"))  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
