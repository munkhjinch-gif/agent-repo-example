"""S-KPISEM first version: a read-only audit of the KPI semantic layer (Cube `indicators_view`, DP-05).

Decision level 1: it only reports. It changes nothing in Cube; fixes go to DPAD and the KPI owners.

Input: the text of `cube_describe_view("indicators_view")`. One measure per line:
  · indicators_view.<name> — <Mongolian term> [нэгж: <unit> · grain: <grain> · <metric id>] ≈ <synonyms>
Synonyms hold the English name, the indicator code (e.g. FIN-017-S2) and its family (FIN).

The checks are heuristics: each finding is a question for the owner, not a verdict. Thresholds, owners and
forums live in Cube `meta` and are not in the describe text, so they are not checked here.
"""

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["HIGH", "MEDIUM", "LOW"]

LINE = re.compile(
    r"^·\s*(?P<view>\w+)\.(?P<name>\w+)\s+—\s+(?P<term>.+?)\s+"
    r"\[нэгж:\s*(?P<unit>.*?)\s+·\s+grain:\s*(?P<grain>\S+)\s+·\s+(?P<metric_id>MET-[A-Z]+-\d+)\]"
    r"(?:\s*≈\s*(?P<synonyms>.*))?$"
)
CODE = re.compile(r"^[A-Z]{3}-\d{3}[A-Z]?(?:-S\d+)?$")
FAMILY = re.compile(r"^[A-Z]{3}$")
RATE_WORDS = ("хувь", "rate", "ratio", "share", "харьцаа")
PERCENT_UNITS = ("хувь",)
RATIO_UNITS = ("дахин", "нэгж (хувийн зөрүү)", "gini", "psi", "hhi", "оноо")
GENERATED_SUFFIX = re.compile(r"_[a-z]{3}_\d{3}[a-z]?_s\d+$")
HELPER_MEASURES = {"indicator_count", "red_count", "amber_count"}  # roll-ups, not indicators


@dataclass(frozen=True)
class Measure:
    name: str
    term: str
    unit: str
    grain: str
    metric_id: str
    english: str | None
    code: str | None
    family: str | None


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    measures: tuple[str, ...]
    detail: str
    question: str  # what the owner has to decide


@dataclass
class AuditReport:
    view: str
    measures: list[Measure]
    findings: list[Finding] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)


def parse(text: str) -> tuple[str, list[Measure], list[str]]:
    view = text.strip().splitlines()[0].strip() if text.strip() else ""
    measures, unparsed = [], []
    in_measures = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("Хэмжигдэхүүн"):
            in_measures = True
            continue
        if line.startswith("Хэмжээс") or line.startswith("⚠"):
            in_measures = False
        if not in_measures or not line.startswith("·"):
            continue
        match = LINE.match(line)
        if not match:
            unparsed.append(line)
            continue
        synonyms = [s.strip() for s in (match["synonyms"] or "").split(",") if s.strip()]
        code = next((s for s in synonyms if CODE.match(s)), None)
        family = next((s for s in synonyms if FAMILY.match(s)), None)
        english = next(
            (s for s in synonyms if s != match["term"] and not CODE.match(s) and not FAMILY.match(s)
             and re.search(r"[A-Za-z]", s) and not re.search(r"[А-Яа-яӨөҮүЁё]", s)),
            None,
        )  # fmt: skip
        measures.append(
            Measure(
                match["name"],
                match["term"].strip(),
                match["unit"].strip(),
                match["grain"],
                match["metric_id"],
                english,
                code,
                family,
            )  # fmt: skip
        )
    return view, measures, unparsed


def _is_rate(measure: Measure) -> bool:
    # The Mongolian term decides (the English name is checked by NAME_DOES_NOT_MATCH_TERM).
    # "хувь хүн" = individual person, not a percentage.
    term = measure.term.lower().replace("хувь хүн", "")
    return any(word in term for word in RATE_WORDS)


def _unit_fits_rate(unit: str) -> bool:
    unit = unit.lower()
    return "/" in unit or any(u in unit for u in PERCENT_UNITS + RATIO_UNITS)  # "/" = per (гомдол/1,000)


def _normalized(term: str) -> str:
    return (
        re.sub(r"\s*\([^)]*\)", "", term).strip().lower()
    )  # "(STP)", "(Cost of Risk)" do not change meaning


def _base_code(code: str) -> str:
    return code.split("-S")[0]


def audit(text: str) -> AuditReport:
    view, measures, unparsed = parse(text)
    report = AuditReport(view, measures, unparsed=unparsed)
    add = report.findings.append
    indicators = [m for m in measures if m.name not in HELPER_MEASURES]

    for m in measures:
        if m.unit.lower() in ("", "unknown"):
            add(Finding("UNIT_UNKNOWN", "HIGH", (m.name,), f"нэгж: '{m.unit or '—'}'",
                        "Энэ үзүүлэлтийн нэгж юу вэ?"))  # fmt: skip
        elif _is_rate(m) and not _unit_fits_rate(m.unit):
            add(Finding("RATE_UNIT_MISMATCH", "HIGH", (m.name,),
                        f"нэр нь хувь/харьцаа ('{m.term}') боловч нэгж '{m.unit}'",
                        "Хувь уу, тоо уу? Нэр эсвэл нэгжийн аль нь буруу вэ?"))  # fmt: skip
        if m.name not in HELPER_MEASURES and m.code is None:
            add(Finding("MISSING_INDICATOR_CODE", "MEDIUM", (m.name,), "synonyms-д индикаторын код алга",
                        "Индикаторын код (V4) аль нь вэ?"))  # fmt: skip
        if m.grain != "daily_snapshot":
            add(Finding("UNEXPECTED_GRAIN", "LOW", (m.name,), f"grain: {m.grain}", "Grain зөв үү?"))

    # Same English name, different Mongolian terms: the measure name does not say what it measures.
    by_english: dict[str, list[Measure]] = defaultdict(list)
    for m in indicators:
        if m.english:
            by_english[m.english].append(m)
    for english, group in sorted(by_english.items()):
        terms = {_normalized(m.term): m.term for m in group}
        if len(group) < 2 or len(terms) < 2:
            continue
        keys = sorted(terms)
        # Only wording differs when one term contains the other: "эрсдэлийн зардал" in
        # "зээлийн эрсдэлийн зардал".
        wording = len(keys) == 2 and (keys[0] in keys[1] or keys[1] in keys[0])
        variants = " / ".join(sorted(terms.values()))
        add(Finding("NAME_DOES_NOT_MATCH_TERM", "MEDIUM" if wording else "HIGH", tuple(m.name for m in group),
                    f"англи нэр '{english}' ижил боловч монгол нэр {len(terms)} янз: {variants}",
                    "Нэг үзүүлэлт үү? Тийм бол нэг нэр; үгүй бол утгад нь тохирох нэр"))  # fmt: skip

    # Same Mongolian term on several measures: readers cannot tell them apart.
    by_term: dict[str, list[Measure]] = defaultdict(list)
    for m in indicators:
        by_term[m.term].append(m)
    for term, group in sorted(by_term.items()):
        if len(group) > 1:
            codes = ", ".join(m.code or "?" for m in group)
            add(Finding("DUPLICATE_TERM", "MEDIUM", tuple(m.name for m in group),
                        f"«{term}» нэр {len(group)} measure-т ({codes})",  # a leading ' is eaten by Sheets
                        "Давхардал уу, эсвэл сегмент/салбарын ялгааг нэрэнд нэмэх үү?"))  # fmt: skip

    # One indicator family (e.g. FIN-019) with metric ids from different domains.
    by_base: dict[str, list[Measure]] = defaultdict(list)
    for m in indicators:
        if m.code:
            by_base[_base_code(m.code)].append(m)
    for base, group in sorted(by_base.items()):
        domains = {m.metric_id.split("-")[1] for m in group}
        if len(domains) > 1:
            add(Finding("METRIC_ID_DOMAIN_MIXED", "MEDIUM", tuple(m.name for m in group),
                        f"{base}: metric id-ийн домэйн {sorted(domains)}",
                        "Аль домэйн (MET-PLAT/MET-RISK...) зөв бэ?"))  # fmt: skip

    generated = [m.name for m in indicators if GENERATED_SUFFIX.search(m.name)]
    if generated:
        add(Finding("GENERATED_NAME", "LOW", tuple(generated),
                    f"{len(generated)} measure-ийн нэр кодоор үүссэн (жишээ: {generated[0]})",
                    "Утга заасан нэр өгөх үү?"))  # fmt: skip

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    report.findings.sort(key=lambda f: (order[f.severity], f.rule, f.measures))
    return report


def to_markdown(report: AuditReport, snapshot: str) -> str:
    counts = {s: sum(f.severity == s for f in report.findings) for s in ("HIGH", "MEDIUM", "LOW")}
    flagged = {name for f in report.findings if f.severity != "LOW" for name in f.measures}
    lines = [
        f"# KPI семантик давхаргын аудит: {report.view}",
        "",
        f"- Эх сурвалж: Cube `cube_describe_view` · {snapshot}"
        " · агент S-KPISEM v0 (зөвхөн уншина, 1-р түвшин)",
        f"- Measure: **{len(report.measures)}** · асуулттай (HIGH/MEDIUM): **{len(flagged)}**",
        f"- Олдвор: HIGH {counts['HIGH']} · MEDIUM {counts['MEDIUM']} · LOW {counts['LOW']}",
        "- Олдвор бүр нь эзэнд тавих асуулт, шийдвэр биш. Босго, эзэмшигч, форумыг (Cube meta) шалгаагүй.",
    ]
    if report.unparsed:
        lines.append(f"- ⚠ Уншиж чадаагүй мөр: {len(report.unparsed)}")
    lines += ["", "| # | Ноцтой | Дүрэм | Measure | Юу олдсон | Эзэнд асуух |", "|---|---|---|---|---|---|"]
    for i, f in enumerate(report.findings, 1):
        names = "<br>".join(f"`{n}`" for n in f.measures[:8]) + (" …" if len(f.measures) > 8 else "")
        lines.append(f"| {i} | {f.severity} | {f.rule} | {names} | {f.detail} | {f.question} |")
    return "\n".join(lines) + "\n"


REVIEW_COLUMNS = ("#", "Ноцтой", "Дүрэм", "Measure-ийн тоо", "Measure", "Юу олдсон", "Эзэнд асуух",
                  "Шийдвэр", "Хариуцагч", "Тайлбар")  # fmt: skip


def to_csv(report: AuditReport, snapshot: str) -> str:
    """Review sheet for DPAD and KPI owners, who fill Шийдвэр / Хариуцагч / Тайлбар (Google Sheets)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([f"Эх сурвалж: Cube {report.view}, {snapshot}. Агент S-KPISEM v0, зөвхөн уншина. "
                     f"{len(report.measures)} measure, {len(report.findings)} олдвор. "
                     "Олдвор бүр нь эзэнд тавих асуулт, шийдвэр биш."])  # fmt: skip
    writer.writerow(["Бөглөх: 'Шийдвэр' баганад Засна / Хэвээр үлдээнэ / Тодруулна гэж бичиж, "
                     "'Хариуцагч' ба 'Тайлбар'-ыг нэмнэ. Бусад баганыг өөрчлөхгүй."])  # fmt: skip
    writer.writerow(REVIEW_COLUMNS)
    for i, f in enumerate(report.findings, 1):
        writer.writerow([i, f.severity, f.rule, len(f.measures), "\n".join(f.measures), f.detail, f.question,
                         "", "", ""])  # fmt: skip
    return buf.getvalue()
