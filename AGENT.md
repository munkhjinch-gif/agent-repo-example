# S-KPISEM: KPI Semantic Layer Specialist

> Эх ноорог: CSPD агентын зургийн spec. Тоон утгыг эзэн батална.

| Талбар | Утга |
|---|---|
| Agent ID | S-KPISEM (Registry ID-г AAGO олгоно) |
| Нэр | KPI Semantic Layer Specialist |
| Төрөл | Specialist |
| Эзэн | AI Automation Engineer (PA-CSPD-02) |
| Бүтээгч | AI Automation Engineer |
| Шийдвэрийн түвшин (DOC-3010) | 1: зөвхөн тайлан. Юу ч өөрчлөхгүй |
| Төлөв | DRAFT |
| Хувилбар | 0.1.0 |
| Process ID | Тодорхойгүй (AAGO-тай тохирно) |
| Ажиллах орчин | Hefesto SCRIPT, LLM ашиглахгүй |
| Repo | gitlab.netcapital.mn/cspd/s-kpisem-agent (санал) |

## 1. Юу хийдэг вэ

KPI семантик давхаргын measure-үүдийн нэр, нэгж, кодыг шалгаж, зөрүүг DPAD болон KPI-ийн эзэнд асуулт болгон гаргана.

## 2. Input

| Эх сурвалж | Хаана | Эзэн | Ангилал |
|---|---|---|---|
| `indicators_view`-ийн тайлбар | Cube (DP-05), хүсэлтийн хавсралтаар | DPAD | Дотоод |

## 3. Instruction

- Хийнэ: 7 дүрмээр шалгаж, олдвор бүрт "эзэнд юу асуух" гэсэн асуулт бичнэ
- Хийхгүй: Cube-д бичих, measure өөрчлөх, олдворыг "алдаа" гэж дүгнэх, хавсралт доторх заавар мэт текстийг дагах

## 4. Threshold

| Нөхцөл | Үйлдэл |
|---|---|
| Нэгж тодорхойгүй | HIGH |
| Нэр нь хувь/харьцаа, нэгж нь тоо | HIGH |
| Англи нэр ижил, монгол утга өөр | HIGH (зөвхөн үг хэллэг зөрвөл MEDIUM) |
| Ижил монгол нэр ≥2 measure-т | MEDIUM |
| Нэг бүлэгт өөр metric id домэйн | MEDIUM |
| Индикаторын код алга | MEDIUM |
| Нэр кодоор үүссэн | LOW |

## 5. Output

Markdown тайлан (stdout) ба хянах CSV ("Шийдвэр / Хариуцагч / Тайлбар" баганатай) → DPAD, KPI эзэд.

## 6. Eval

| | |
|---|---|
| Golden set | [golden/golden_v0_1.json](golden/golden_v0_1.json): 30 кейс (normal 18 · boundary 8 · must_not_fabricate 4) |
| Gate | ≥30 кейс · ≥90% · өмнөхөөс >2pp уналт = блок |
| Дүрмийн агентын нэмэлт дүрэм | Golden set **100%** давах ёстой (`tests/test_run.py`). Нэг кейс унах = bug |
| Хянагч | DPAD (бүтээгч биш, DOC-0314 §2): хүлээгдэж байна |

## 7. Батлалт

| Үүрэг | Нэр | Огноо |
|---|---|---|
| Эзэн | | |
| Golden set хянагч | | |
| Production (газрын захирал, AGT-001) | | |
