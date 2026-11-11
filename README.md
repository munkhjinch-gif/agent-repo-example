# S-KPISEM: KPI Semantic Layer Specialist (жишээ repo)

> **Энэ бол CSPD-ийн агентын repo ямар бүтэцтэй байхыг харуулах ЖИШЭЭ.** Агуулга нь S-KPISEM v0
> (KPI семантик давхаргын аудит). Шинэ агент бүтээхдээ энэ бүтцийг хуулж, агуулгыг солино.

## Юу хийдэг вэ

Cube `indicators_view`-ийн (DP-05) тайлбарыг уншиж, KPI-ийн нэр, нэгж, кодын зөрүүг **эзэнд тавих асуулт**
болгон тайлагнана. Cube-д юу ч өөрчлөхгүй (шийдвэрийн 1-р түвшин). Дэлгэрэнгүй: [AGENT.md](AGENT.md).

| | |
|---|---|
| Эзэн | AI Automation Engineer (PA-CSPD-02) |
| Төлөв | DRAFT |
| Ажиллах орчин | Hefesto, SCRIPT горим (LLM ашиглахгүй) |
| Хамаарал | Зөвхөн Python 3.11+ стандарт сан |

## Ажиллуулах

```sh
# Агент (Hefesto яг ингэж дуудна)
INPUT_ATTACHMENTS_DIR=<cube_describe_view-ийн .txt байгаа хавтас> python3 agent/run.py

# Golden set + release gate
python3 eval/run_eval.py

# Тест
python3 -m pytest
```

## Бүтэц

| Зам | Юу | Хэн хөтөлнө |
|---|---|---|
| [README.md](README.md) | Энэ файл: агент юу хийдэг, хэрхэн ажиллуулах | Бүтээгч |
| [AGENT.md](AGENT.md) | Агентын "иргэний үнэмлэх": Registry талбар, Input / Instruction / Threshold | Эзэн батална |
| [CHANGELOG.md](CHANGELOG.md) | Хувилбар бүр: өөрчлөлт, Eval-ийн үр дүн, батлалт. Rollback-ийн үндэс | Бүтээгч |
| [CLAUDE.md](CLAUDE.md) | Claude Code-оор хөгжүүлэх дүрэм | Бүтээгч |
| [hefesto-agent.json](hefesto-agent.json) | Hefesto-гийн манифест. **Repo-гийн үндэст байх ёстой** | Бүтээгч |
| [hefesto-spec.md](hefesto-spec.md) | Hefesto-д ачаалагдах заавар (Redeploy үед) | Бүтээгч, эзэн батална |
| [agent/](agent/) | Код: `run.py` (Hefesto-гийн эхлэх цэг), `audit.py` (логик) | Бүтээгч |
| [golden/](golden/) | Golden set (≥30 кейс) ба түүний README | Эзэн бэлтгэнэ, **өөр хүн** хянана |
| [eval/](eval/) | Golden set ажиллуулж gate шалгах скрипт. Тайлан `eval/reports/`-д (git-д орохгүй) | Бүтээгч |
| [tests/](tests/) | Автомат тест. **Зөвхөн синтетик өгөгдөл** | Бүтээгч |
| [docs/](docs/) | Registry Draft багц, runbook | Бүтээгч |

## Хэзээ ч repo-д оруулахгүй

- Нууц мэдээлэл: токен, нууц үг, `.env`. Hefesto-оос `CONN_*` хувьсагчаар ирнэ
- Бодит өгөгдөл: Cube-ийн бодит гаралт, харилцагч, KPI-ийн тоо
- Prompt-ын батлагдсан хувилбар нь NetBrain SI-01-д (DOC-3011); `hefesto-spec.md` нь түүний хуулбар
