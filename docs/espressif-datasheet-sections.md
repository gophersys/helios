# Datasheet Section Survey (targeted-PDF-extraction prep)

Survey of all 15 PDFs in `data/datasheets/` (2026-07-30). Extraction via `pdftotext -layout`;
page numbers below are **PDF page indices** (1-based, `\f`-separated pdftotext pages, matching
`pdfinfo` page count), not the printed page numbers.

## Headline findings

1. **All 15 PDFs extract clean text.** None are scanned images. Every file yields 90-220 KB of
   text with intact headings and `-layout` keeps table columns aligned.
2. **14 of 15 datasheets are Chinese.** The manifest's `language` field is wrong for 12 files:
   it claims `en` for most, but only `esp32-c3.pdf` is actually English (0% CJK). All others are
   27-51% CJK characters. These are the zh_CN editions Espressif publishes via LCSC/szlcsc.
   The flagged `esp32-wroom-32e.pdf` (zh) is unremarkable — it extracts as well as the rest.
   **Consequence: the section finder must match Chinese headings as the primary pattern set;**
   English is the exception, not the rule. Chinese and English editions share identical section
   numbering, so patterns pair 1:1.
3. Every page carries a **running header repeating the current chapter heading** (e.g.
   `3 管脚定义` at the top of every page of chapter 3). This is the most robust range signal:
   a chapter's page range = {pages whose running header matches it}. No look-ahead heuristics
   needed.
4. Overall context savings: **298 of 750 total pages (~40%)** go to the LLM when extracting the
   four target sections. Trimming RF subsections out of legacy electrical chapters (see
   outliers) brings it to roughly one third.

## Summary table

| File | Type | Lang (actual) | Pages | Pin definitions | Strapping / boot | Electrical & power | Peripherals | LLM pages | Ratio |
|---|---|---|---:|---|---|---|---|---:|---:|
| esp32-wroom-32.pdf | module | zh | 27 | `2 管脚定义` p8-11 | `2.3 Strapping 管脚` p10-11 | `5 电气特性` p14-16 | `4 外设接口和传感器` p13 | 8 | 30% |
| esp32-wroom-32e.pdf | module | zh | 48 | `3 管脚定义` p10-12 | `4 启动配置项` p13-16 | `6 电气特性` p26-27 | `5 外设` p17-25 | 18 | 38% |
| esp32-s2-wroom.pdf | module | zh | 32 | `3 管脚定义` p9-13 | `3.3 Strapping 管脚` p11-13 | `4 电气特性` p14-19 | — (defers to chip DS) | 11 | 34% |
| esp32-s3-wroom-1.pdf | module | zh | 37 | `3 管脚定义` p10-15 | `3.3 Strapping 管脚` p13-15 | `4 电气特性` p16-25 | — (defers to chip DS) | 16 | 43% |
| esp32-s3-mini-1.pdf | module | zh | 37 | `3 管脚定义` p10-15 | `3.3 Strapping 管脚` p13-15 | `4 电气特性` p16-25 | — (defers to chip DS) | 16 | 43% |
| esp32-c3-wroom-02.pdf | module | zh | 42 | `3 管脚定义` p10-11 | `4 启动配置项` p12-14 | `6 电气特性` p20-22 | `5 外设` p15-19 | 13 | 31% |
| esp32-c3-mini-1.pdf | module | zh | 42 | `3 管脚定义` p10-11 | `4 启动配置项` p12-14 | `6 电气特性` p20-22 | `5 外设` p15-19 | 13 | 31% |
| esp32-c6-wroom-1.pdf | module | zh | 37 | `3 管脚定义` p10-14 | `3.3 Strapping 管脚` p11-14 | `4 电气特性` p15-17 | — (defers to chip DS) | 8 | 22% |
| esp32-h2-mini-1.pdf | module | zh | 34 | `3 管脚定义` p10-14 | `3.3 Strapping 管脚` p11-14 | `4 电气特性` p15-17 | — (defers to chip DS) | 8 | 24% |
| esp32.pdf | chip | zh | 74 | `2 管脚` p12-21 | `3 启动配置项` p22-25 | `5 电气特性` p50-56 ¹ | `4.8 数字外设`…`4.10 外设管脚分配` p36-49 | 35 | 47% |
| esp32-s2.pdf | chip | zh | 52 | `2 管脚定义` p12-18 | `2.4 Strapping 管脚` p17-18 | `4 电气特性` p35-41 ¹ | `3.3 模拟外设`…`3.10 外设管脚分配` p21-34 | 28 | 54% |
| esp32-s3.pdf | chip | zh | 79 | `2 管脚` p14-28 | `3 启动配置项` p29-31 | `5 电气特性` p60-64 | `4.2 外设` p46-57 | 35 | 44% |
| esp32-c3.pdf | chip | **en** | 69 | `2 Pins` p12-25 | `3 Boot Configurations` p26-28 | `5 Electrical Characteristics` p50-54 | `4.2 Peripherals` p42-47 | 28 | 41% |
| esp32-c6.pdf | chip | zh | 77 | `2 管脚` p13-27 | `3 启动配置项` p28-31 | `5 电气特性` p58-62 | `4.2 外设` p44-53 | 34 | 44% |
| esp32-h2.pdf | chip | zh | 63 | `2 管脚` p12-21 | `3 启动配置项` p22-24 | `5 电气特性` p50-53 | `4.2 外设` p39-48 | 27 | 43% |
| **Total** | | | **750** | | | | | **298** | **40%** |

¹ Legacy chapters embed RF subsections (`5.6 Wi-Fi 射频` etc. / `4.8 Wi-Fi 射频`) inside the
electrical chapter; range shown stops before them where a clean boundary exists (esp32: RF
starts p52 within ch. 5 — range keeps DC + power pages p50-56 up to `6 封装` p57). The slim
module template similarly puts `4.5 Wi-Fi 射频`/`4.6 低功耗蓝牙射频` inside `4 电气特性`
(s3-wroom-1/s3-mini-1 p19-25), so trimming at the first RF subheading saves ~6 more pages each.

LLM pages = union of the four ranges (they can overlap: strapping subsection lives inside the
pins chapter in the slim-module and s2-chip templates).

## Document templates (structural families)

- **Modern chip DS** (esp32-c3/c6/h2/s3, and esp32 partially):
  `1 型号对比/Series Comparison` → `2 管脚/Pins` (subsections 管脚布局, 管脚概述, IO 管脚,
  模拟管脚, 电源, 芯片与 flash 的管脚对应关系) → `3 启动配置项/Boot Configurations` →
  `4 功能描述/Functional Description` (with `4.2 外设/Peripherals`, `4.3 无线通信/Wireless
  Communication`) → `5 电气特性/Electrical Characteristics` → `6 射频特性/RF Characteristics`
  → `7 封装/Packaging`.
- **Full module DS** (wroom-32e, c3-wroom-02, c3-mini-1):
  `1 模组概述` → `2 功能框图` → `3 管脚定义` → `4 启动配置项` → `5 外设` (5.1 外设概述,
  5.2 外设描述) → `6 电气特性` → `7 射频特性` → schematics/dimensions/handling.
- **Slim module DS** (s2-wroom, s3-wroom-1, s3-mini-1, c6-wroom-1, h2-mini-1):
  `3 管脚定义` (3.1 管脚布局, 3.2 管脚描述|管脚定义, **3.3 Strapping 管脚**) →
  `4 电气特性` (incl. RF subsections) → `5 模组原理图` → … **No peripherals chapter** —
  body text explicitly defers: 「外设管脚分配请参考《…系列芯片技术规格书》」.
- **Legacy** (esp32-wroom-32 v3.x, esp32-s2 chip): strapping is a *subsection of the pins
  chapter* (`2.3` / `2.4 Strapping 管脚`), peripherals are scattered subsections
  (`模拟外设`/`数字外设`/`外设管脚分配`) inside `功能描述`, RF is inside the electrical chapter.

## Recommended heading-regex set

Applied line-by-line to `pdftotext -layout` output. All patterns are full-line anchored.

**Pre-filters (mandatory):**
```
TOC/LoT line   :  \s{2,}\d{1,3}\s*$   or   \.{3,}        -> reject (headings repeat in TOC with trailing page no.)
Heading shape  :  ^\s{0,10}(\d+(?:\.\d+){0,2})\s+(<title-alternation>)\s*$
```
Do **not** accept generic `^\d+\s+.*` as a heading: table footnotes (`1 P：电源；I：输入…`),
pin-table rows (`14 GPIO12  I/O/T …`) and revision-history rows all mimic numbered headings.
Match only whitelisted titles.

**Target sections (zh|en, in priority order per target):**
```
pins        (top)  ^\d+\s+(?:管脚定义|管脚|Pins)\s*$
pins-table  (sub)  ^\d+\.\d+\s+(?:管脚描述|管脚定义|管脚概述|Pin\s+(?:Overview|Description))\s*$
strapping   (top)  ^\d+\s+(?:启动配置项|Boot\s+Configurations)\s*$
strapping   (sub)  ^\d+\.\d+\s+(?:Strapping\s*管脚|Strapping\s+Pins)\s*$        # fallback if no top-level hit
electrical  (top)  ^\d+\s+(?:电气特性|Electrical\s+Characteristics)\s*$
power       (sub)  ^\d+\.\d+\s+(?:功耗特性|Current\s+Consumption|Active\s*模式下的\s*RF\s*功耗)\s*$
periph      (top)  ^\d+\s+(?:外设|外设接口和传感器)\s*$
periph      (sub)  ^\d+\.\d+\s+(?:外设|Peripherals)\s*$                          # modern chip DS
periph-legacy(sub) ^\d+\.\d+\s+(?:模拟外设|数字外设|外设管脚分配)\s*$              # esp32 / esp32-s2 chip
```

**Range-end boundaries:**
- Top-level chapter: end = last page whose **running header** repeats `N <title>` (chapter
  title recurs atop every page — the most reliable signal in these PDFs). Equivalent fallback:
  page before the first page of the next whitelisted top-level heading.
- `Strapping 管脚` subsection: ends with its parent pins chapter.
- `4.2 外设/Peripherals`: ends at `^\d+(?:\.\d+)?\s+(?:无线通信|Wireless\s+Communication)`.
- Legacy peripherals run: from first `模拟外设|数字外设` to page before the `电气特性` chapter.
- Optional electrical trim: stop at first `^\d+\.\d+\s+(?:Wi-?Fi\s*射频|低功耗蓝牙射频|蓝牙射频|射频…)`
  subheading to drop RF tables from legacy/slim-template electrical chapters.

**Naming migration note:** Espressif renamed the strapping chapter — esp32.pdf's revision
history states 「章节 3 启动配置项（曾用名 "Strapping 管脚"）」. Both alternations are required
indefinitely.

## Structural outliers / failure modes

1. **Manifest language field is unreliable** — 12 of 13 files marked `en` are Chinese. Detect
   language from extracted text (CJK ratio), not the manifest.
2. **Slim-template modules have no peripherals section** (s2-wroom, s3-wroom-1, s3-mini-1,
   c6-wroom-1, h2-mini-1). The extractor must fall through to the corresponding *chip*
   datasheet for peripheral info.
3. **esp32-wroom-32.pdf** is the oldest template: strapping is `2.3` inside the pins chapter,
   peripherals is a single-page table (`4 外设接口和传感器` p13), and there is no
   启动配置项/外设 chapter. All four regex fallbacks above are exercised only by this file and
   esp32-s2.pdf.
4. **esp32-s2.pdf** (chip) is the only chip DS without a boot-configuration chapter (strapping
   = `2.4`) and with peripherals scattered across `3.3`-`3.10`; its widest useful range
   (`3.3 模拟外设` → `3.10 外设管脚分配`, p21-34) drags in RTC/timers/crypto subsections —
   acceptable overshoot, or match `3.3`, `3.4`, `3.10` individually.
5. **TOC + List-of-Tables pages (p3-10) repeat every heading**, including table titles like
   `3 Strapping 管脚` that collide with heading numbers. The trailing-page-number pre-filter
   handles all observed cases.
6. **Footnotes and pin-table rows mimic numbered headings** (`1 P：电源…`, `14 GPIO12 …`,
   revision rows `2022.03 v3.3 …`). Whitelist-title matching is required; generic numeric
   heading detection mis-terminates ranges.
7. Boundary pages are shared: a chapter can start mid-page where the previous one ends. Ranges
   above are inclusive of boundary pages; the union handles double counting.
