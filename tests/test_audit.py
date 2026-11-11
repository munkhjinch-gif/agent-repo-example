"""S-KPISEM v0 audit rules on a SYNTHETIC describe output (the real Cube metadata stays out of the repo)."""

from agent.audit import audit, parse, to_markdown

HEADER = "demo_view\nСинтетик view.\n\nХэмжигдэхүүн (9):\n"
FOOTER = (
    "\nХэмжээс (1):\n· demo_view.snapshot_date — тайлант огноо\n"
    "\n⚠ Ашиглалтын хориг:\n· Олон өдрийг нийлбэрлэхгүй\n"
)


def line(name: str, term: str, unit: str, metric: str, synonyms: str, grain: str = "daily_snapshot") -> str:
    return f"· demo_view.{name} — {term} [нэгж: {unit} · grain: {grain} · {metric}] ≈ {synonyms}\n"


GOOD = line("loan_growth", "Зээлийн өсөлт", "хувь 0–100 (×100 хийхгүй)", "MET-PLAT-0001",
            "Loan Growth, AAA, AAA-001, Зээлийн өсөлт")  # fmt: skip


def run(*lines: str):  # type: ignore[no-untyped-def]
    return audit(HEADER + "".join(lines) + FOOTER)


def rules(report) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return {f.rule: f.severity for f in report.findings}


def test_parses_measures_and_ignores_dimensions() -> None:
    view, measures, unparsed = parse(HEADER + GOOD + FOOTER)
    assert view == "demo_view" and unparsed == []
    (m,) = measures
    assert (m.name, m.code, m.family, m.english, m.metric_id) == (
        "loan_growth", "AAA-001", "AAA", "Loan Growth", "MET-PLAT-0001")  # fmt: skip


def test_clean_measure_has_no_findings() -> None:
    assert run(GOOD).findings == []


def test_unknown_unit_is_high() -> None:
    report = run(line("x", "Аудитын бэлэн байдал", "unknown", "MET-PLAT-0002", "Audit, AAA, AAA-002"))
    assert rules(report) == {"UNIT_UNKNOWN": "HIGH"}


def test_percentage_with_a_count_unit_is_high() -> None:
    report = run(line("x", "Идэвхжлийн хувь", "хэрэглэгч", "MET-PLAT-0003", "Activation, AAA, AAA-003"))
    assert rules(report) == {"RATE_UNIT_MISMATCH": "HIGH"}


def test_no_false_alarm_for_individual_person_or_per_unit() -> None:
    report = run(
        line(
            "a",
            "Эмэгтэй хувь хүн зээлдэгчийн багц",
            "тэрбум ₮",
            "MET-PLAT-0004",
            "Female Portfolio, AAA, AAA-004",
        ),
        line(
            "b", "Гомдлын түвшин", "гомдол/1,000 харилцагч", "MET-PLAT-0005", "Complaint Rate, AAA, AAA-005"
        ),
        line("c", "Хөшүүргийн харьцаа", "дахин", "MET-PLAT-0006", "Leverage, AAA, AAA-006"),
    )
    assert report.findings == []


def test_same_english_name_with_different_meaning_is_high() -> None:
    report = run(
        line("npl", "Чанаргүй зээлийн хувь", "хувь", "MET-PLAT-0007", "NPL Ratio, AAA, AAA-007"),
        line("npl_s1", "Босго давсан салбарын тоо", "салбар", "MET-PLAT-0008", "NPL Ratio, AAA, AAA-007-S1"),
    )
    assert rules(report)["NAME_DOES_NOT_MATCH_TERM"] == "HIGH"


def test_only_wording_differs_is_medium_and_brackets_are_ignored() -> None:
    report = run(
        line("cor", "Эрсдэлийн зардал", "хувь", "MET-PLAT-0009", "Cost of Risk, AAA, AAA-008"),
        line(
            "cor_s1",
            "Зээлийн эрсдэлийн зардал (Cost of Risk)",
            "хувь",
            "MET-PLAT-0010",
            "Cost of Risk, AAA, AAA-008-S1",
        ),  # fmt: skip
        line("stp", "Шууд боловсруулалтын хувь", "хувь", "MET-PLAT-0011", "STP Rate, AAA, AAA-009"),
        line(
            "stp_s1", "Шууд боловсруулалтын хувь (STP)", "хувь", "MET-PLAT-0012", "STP Rate, AAA, AAA-009-S1"
        ),
    )
    names = [f for f in report.findings if f.rule == "NAME_DOES_NOT_MATCH_TERM"]
    assert len(names) == 1 and names[0].severity == "MEDIUM" and "cor" in names[0].measures


def test_duplicate_terms_mixed_metric_domains_and_generated_names() -> None:
    report = run(
        line("t", "Төвлөрөл", "хувь", "MET-PLAT-0013", "Concentration, AAA, AAA-010"),
        line("t_aaa_010_s1", "Төвлөрөл", "хувь", "MET-RISK-0014", "Concentration, AAA, AAA-010-S1"),
    )
    assert rules(report) == {
        "DUPLICATE_TERM": "MEDIUM",
        "METRIC_ID_DOMAIN_MIXED": "MEDIUM",
        "GENERATED_NAME": "LOW",
    }


def test_missing_code_is_flagged_but_helper_counts_are_not() -> None:
    report = run(
        line("no_code", "Код байхгүй", "тоо", "MET-PLAT-0015", "No Code"),
        line("red_count", "Улаан индикаторын тоо", "count", "MET-RISK-0016", "red KPI"),
    )
    assert [f.measures for f in report.findings] == [("no_code",)]


def test_unparsable_measure_lines_are_reported() -> None:
    report = run(GOOD, "· demo_view.broken — нэгжгүй мөр\n")
    assert len(report.measures) == 1 and len(report.unparsed) == 1
    assert "Уншиж чадаагүй мөр: 1" in to_markdown(report, "2026-11-09")


def test_markdown_lists_each_finding_with_a_question() -> None:
    report = run(line("x", "Хувь", "unknown", "MET-PLAT-0017", "X, AAA, AAA-011"))
    markdown = to_markdown(report, "2026-11-09")
    assert "| 1 | HIGH | UNIT_UNKNOWN | `x` |" in markdown and "Эзэнд асуух" in markdown
