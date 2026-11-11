"""Run the golden set against the agent and apply the release gate.

Usage:
  python eval/run_eval.py                                   # golden/golden_v0_1.json
  python eval/run_eval.py --baseline eval/reports/<prev>.json   # regression check vs last release

Gate (CSPD agent map, P-AIAE / S-EVAL specs): ≥30 cases · pass rate ≥90% (decision level 3: ≥95%) ·
a drop of more than 2 pp against the baseline blocks. Exit 0 = PASS, 2 = BLOCKED.
Standard library only.
"""

import argparse
import contextlib
import io
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import run  # noqa: E402
from agent.audit import audit  # noqa: E402

MIN_CASES = 30
HEADER = "golden_view\nСинтетик.\n\nХэмжигдэхүүн:\n"
FOOTER = "\nХэмжээс (1):\n· golden_view.snapshot_date — огноо\n"


def text_of(case: dict) -> str:
    return case["raw"] if "raw" in case else HEADER + "".join(line + "\n" for line in case["input"]) + FOOTER


def check(case: dict) -> tuple[bool, str]:
    if "expected_exit" in case:  # run the whole Hefesto entry point
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp, "in")
            inbox.mkdir()
            (inbox / "input.txt").write_text(text_of(case), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = run.main({"INPUT_ATTACHMENTS_DIR": str(inbox), "KPISEM_OUT_DIR": str(Path(tmp, "out"))})
        return code == case["expected_exit"], f"exit {code}, expected {case['expected_exit']}"
    actual = sorted({(f.rule, f.severity) for f in audit(text_of(case)).findings})
    expected = sorted({(f["rule"], f["severity"]) for f in case["expected_findings"]})
    return actual == expected, f"got {actual}, expected {expected}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--golden", type=Path, default=ROOT / "golden" / "golden_v0_1.json")
    parser.add_argument("--baseline", type=Path, help="report JSON of the last released version")
    args = parser.parse_args(argv)

    golden = json.loads(args.golden.read_text(encoding="utf-8"))
    level = int(golden["_meta"].get("decision_level", 1))
    results = []
    for case in golden["cases"]:
        ok, detail = check(case)
        results.append({"id": case["id"], "category": case["category"], "passed": ok, "detail": "" if ok else detail})

    total, passed = len(results), sum(r["passed"] for r in results)
    rate = passed / total if total else 0.0
    required = 0.95 if level >= 3 else 0.90
    reasons = []
    if total < MIN_CASES:
        reasons.append("GOLDEN_SET_TOO_SMALL")
    if rate < required:
        reasons.append("PASS_RATE_BELOW_THRESHOLD")
    if args.baseline:
        previous = json.loads(args.baseline.read_text(encoding="utf-8"))["pass_rate"]
        if round((previous - rate) * 100, 6) > 2.0:
            reasons.append("REGRESSION_VS_PREVIOUS")

    report = {
        "agent": golden["_meta"].get("agent"),
        "golden_version": golden["_meta"].get("version"),
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "total": total,
        "passed": passed,
        "pass_rate": round(rate, 4),
        "required": required,
        "gate": "PASS" if not reasons else "BLOCKED",
        "reasons": reasons,
        "cases": results,
    }
    out = ROOT / "eval" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"eval_{report['run_at'][:19].replace(':', '').replace('-', '')}Z.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    for r in results:
        if not r["passed"]:
            print(f"FAIL {r['id']} ({r['category']}): {r['detail']}")
    print(f"{report['agent']}: {passed}/{total} ({rate:.1%}), required ≥{required:.0%} → {report['gate']}"
          + (f" {reasons}" if reasons else ""))  # fmt: skip
    print(f"Report: {path.relative_to(ROOT)}")
    return 0 if not reasons else 2


if __name__ == "__main__":
    raise SystemExit(main())
