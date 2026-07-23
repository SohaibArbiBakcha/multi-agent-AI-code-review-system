# CodeSentinel — Architecture & Build Notes

This document explains, in detail, what CodeSentinel does, how it's built, and the
reasoning behind the design decisions. Think of it as the technical deep-dive that
doesn't fit in a README: the "why" behind every module, not just the "what."

---

## 1. What this project is

CodeSentinel is a **multi-agent AI code review system** that runs entirely on local
infrastructure — no OpenAI/Anthropic/Google API key, no cloud bill, no code ever
leaving the machine it runs on. You upload a source file (any language), and five
specialized agents analyze it in parallel/sequential phases, producing:

- A list of bugs and security vulnerabilities, each explained in plain language
- A list of code smells (long functions, duplication, bad naming, magic numbers, god classes) with refactor suggestions
- Complexity metrics (cyclomatic complexity, maintainability index, Halstead metrics) and a letter grade
- A generated unit test file covering the submitted code
- A synthesized, pedagogical Markdown/PDF report tying it all together
- A single 0–100 quality score with a transparent, auditable formula behind it

The whole thing runs through a **Streamlit** dashboard and is powered by **Ollama**
serving two open-weight models locally: **Qwen2.5-Coder:7b** (code analysis/generation)
and **Mistral:7b** (report writing).

### Why build this instead of just using SonarQube?

SonarQube, Pylint, ESLint and friends are excellent at *detecting* problems, but they
report them as terse, rule-ID-labeled messages (`R0913: Too many arguments (7/5)`) with
no explanation of *why it matters* or *how to think about fixing it*. That's fine for a
senior engineer skimming a CI report; it's not very useful for someone still learning.
CodeSentinel's entire reason for existing is to sit on top of that detection layer and
translate it into something a person can actually learn from — while staying free to
run repeatedly and private enough that nobody has to think twice about uploading their
code to a third party.

---

## 2. High-level architecture

The system is organized into four strictly layered modules, each only talking to the
layer directly below it:

```
┌─────────────────────────────────────────────┐
│               PRESENTATION LAYER             │
│           Streamlit dashboard (ui/)          │
└──────────────────────┬───────────────────────┘
                        │
┌──────────────────────▼───────────────────────┐
│             ORCHESTRATION LAYER               │
│      LangGraph state machine (orchestrator/)  │
└──────────────────────┬───────────────────────┘
                        │
┌──────────────────────▼───────────────────────┐
│                 AGENT LAYER                   │
│   5 specialized agents (agents/)              │
└──────────────────────┬───────────────────────┘
                        │
┌──────────────────────▼───────────────────────┐
│            TOOLS & LLM LAYER                  │
│  Pylint · Bandit · Radon · AST · Ollama       │
│  (tools/, llm/)                               │
└────────────────────────────────────────────────┘
```

Why this shape, specifically:

- **Presentation never touches business logic.** `ui/pages/*.py` only reads/writes
  `st.session_state` and calls into `orchestrator.graph`. This means the entire
  analysis pipeline can be exercised — and was, via the test suite — without ever
  starting Streamlit.
- **Orchestration doesn't know how agents work internally.** It just calls `agent.run(...)`
  and merges the returned dict into shared state. You could rewrite any agent's
  internals completely and the orchestrator wouldn't need to change.
- **Agents don't talk to subprocesses or HTTP directly.** They call into `tools/` and
  `llm/`, which own all the messy I/O (spawning `pylint` as a subprocess, parsing its
  JSON, calling the Ollama HTTP API, retrying on malformed responses). This meant that
  when I hit a bug in how the LLM's JSON output was being parsed, the fix lived in
  exactly one file (`llm/ollama_client.py`) instead of being duplicated across five
  agents.

---

## 3. The orchestrator: LangGraph and the three-phase pipeline

The core coordination logic lives in `orchestrator/graph.py`, built on LangGraph's
`StateGraph`. I picked LangGraph over hand-rolling `asyncio.gather()` calls for two
reasons: its execution model (a graph of nodes reading/writing a shared typed state,
executed in "supersteps" — everything with satisfied dependencies runs together, then
the state merges before the next step) maps *exactly* onto the phase structure I
wanted, and it comes with `draw_mermaid()`, which I used constantly during development
to sanity-check the graph topology before wiring up real agent logic.

### The state object

```python
class CodeSentinelState(TypedDict, total=False):
    input_code: str
    language: str
    filename: str
    agent1_result: list[dict]   # BugHunter
    agent2_result: list[dict]   # CodeSmell
    agent3_result: dict         # Complexity
    agent4_result: str          # TestGenerator (raw test file content)
    agent5_result: dict         # ReportWriter ({"markdown": ...})
    score: dict
    status: str
    logs: list[str]
```

Every node receives the *entire* state and returns a *partial* update (just the keys
it owns). LangGraph merges these automatically. This is what lets Phase 1's three
agents run concurrently without stepping on each other — they each only ever write to
their own `agentN_result` key.

### The three phases

```
START ──┬──▶ bug_hunter  ──┐
        ├──▶ code_smell  ──┼──▶ test_generator ──▶ report_writer ──▶ END
        └──▶ complexity  ──┘
```

- **Phase 1 (parallel):** `bug_hunter`, `code_smell`, `complexity` all read only the
  raw source code — none of them depend on each other's output — so they're wired
  directly off `START` and all converge on `test_generator`. LangGraph detects there's
  no dependency between them and executes them in the same superstep. In practice this
  roughly triples the throughput of this phase, since each agent spends most of its
  wall-clock time waiting on an LLM response, and that waiting overlaps.
- **Phase 2 (sequential):** `test_generator` runs after Phase 1 converges, because it
  benefits from knowing what functions exist (extracted via AST) before generating
  tests for them.
- **Phase 3 (sequential):** `report_writer` runs last because it aggregates *everything*
  — all four previous results plus the computed score — into one coherent narrative.
  It structurally cannot run any earlier.

### Timeout handling and graceful degradation

Every node is wrapped by `_with_timeout()`, which runs the agent in a worker thread via
`ThreadPoolExecutor` and enforces a configurable timeout (120s by default,
`AGENT_TIMEOUT_SECONDS` env var). If Ollama hangs, is unreachable, or a single agent
throws, the wrapper catches it and returns a safe fallback value (`[]`, `{}`, or a
placeholder string) instead of propagating the exception. This was a deliberate design
choice: **a single stuck agent should never take down the whole analysis.** The
pipeline always finishes; worst case, one section of the report says "unavailable"
instead of the entire upload failing with a stack trace.

---

## 4. The five agents

Each agent lives in its own file under `agents/`, follows the same rough shape
(gather raw signal → build a prompt → call the LLM → validate/structure the response),
and exposes a single `run(...)` function. Two code paths exist in every agent: one for
Python (which has real static-analysis tooling behind it) and one generic path for
every other language (LLM does the detection directly). More on that in §6.

### Agent 1 — BugHunter (`agents/bug_hunter.py`)

For Python: runs **Pylint** and **Bandit** as subprocesses (JSON output), then — this
was a deliberate choice after experimentation — sends **each finding individually** to
the LLM for explanation, rather than dumping the whole list in one prompt. I tried the
batched version first; the per-issue explanations were noticeably vaguer and less
localized.

That decision had a real cost I didn't catch until running the pipeline against an
actual Ollama server: `bad_code.py` produces 17 findings (12 from Pylint, 5 from
Bandit), and a single explanation call measured live at ~16s on an RTX 4060. Run
sequentially, that's ~280s — well past the orchestrator's 120s per-agent timeout — so
BugHunter was silently timing out and returning **zero bugs** on a file that had 17
real ones. The Phase 1 parallelism (§4 below) only overlaps BugHunter against
CodeSmell/Complexity; it does nothing for the 17 sequential calls happening *inside*
BugHunter itself. Fixed by explaining findings concurrently with a small
`ThreadPoolExecutor` (`MAX_WORKERS = 4`) and capping the number of findings explained
per run (`MAX_FINDINGS = 20`) to bound worst-case latency on pathological files. Same
file, same hardware, same models: ~77s and all 17 bugs returned correctly.

### Agent 2 — CodeSmell (`agents/code_smell.py`)

For Python: detection is 100% deterministic, done by walking the AST directly
(`tools/ast_parser.py`) — long functions (>40 lines), duplicate code blocks (via
`difflib.SequenceMatcher`, similarity ≥ 0.85), god classes (>12 methods), magic
numbers, bad naming. The LLM only comes in afterward to *refine severity* and *suggest
a refactor*, with a strict guard: if the LLM's response doesn't have the exact same
number of items as the input list, the raw heuristic output is used instead. I added
that guard after seeing the model occasionally drop an item mid-list.

### Agent 3 — Complexity (`agents/complexity.py`)

For Python: **Radon** computes real cyclomatic complexity, maintainability index, and
Halstead metrics — these are deterministic measurements, not LLM guesses. The letter
grade (A–F) is derived from the maintainability index via fixed thresholds, also
deterministic. The LLM's only job here is to look at the list of complexity scores per
function and name the top 3 "hotspots" in plain language.

### Agent 4 — TestGenerator (`agents/test_generator.py`)

Extracts function signatures via AST, then asks the LLM to write a full test file
covering each one (happy path, edge case, error case). The important part: **every
generated Python test is validated with `ast.parse()` before being accepted.** If it
doesn't parse, it's discarded and replaced with an explicit error message rather than
silently handing the user broken code labeled as a "generated test." This mattered in
practice — LLM-generated tests occasionally choke on functions with `*args`/`**kwargs`,
complex default arguments, or, in one case caught during live testing, seven positional
arguments the model itself got confused writing assertions for.

The fence-stripping helper (`_strip_fences`) also had to be hardened after a live run:
despite the prompt explicitly saying "no explanation, no markdown," the model routinely
prepends a sentence of French prose before the ` ```python ` block anyway (*"Voici un
exemple de fichier de tests pytest..."*). The original implementation only stripped a
fence if the response *started* with one, so that prose leaked straight into the
"generated test" and broke `ast.parse()` on line 1 every time — the failure looked like
a code-generation bug but was actually an extraction bug. Fixed by searching for the
fenced block anywhere in the response (`re.search` instead of `str.startswith`), the
same lesson §7 already applies to JSON extraction, just not yet applied here at the
time.

### Agent 5 — ReportWriter (`agents/report_writer.py`)

Aggregates all four previous outputs plus the computed score and asks **Mistral:7b**
(picked specifically for French-language generation quality — this started as a
French-language academic project) to write a structured Markdown report. The system
prompt explicitly instructs the model not to invent information absent from the
provided data, to reduce hallucination risk on what is effectively an evaluative
document.

---

## 5. Scoring: why it's a formula, not another LLM call

```
score = (100 − bug_penalty)   × 0.30
      + (100 − smell_penalty) × 0.25
      + maintainability_index × 0.25
      + testability_score     × 0.20

bug_penalty   = min(100, bugs_count × 10 + critical_bugs × 25)
smell_penalty = min(100, smells_count × 5 + high_smells × 15)
testability   = 100 if avg_cyclomatic_complexity <= 8 else 50
```

I could have just asked the LLM "give this code a score out of 100." I didn't, on
purpose: a score that comes out of an LLM call is **not reproducible** — run the exact
same file twice and you might get 82 one time and 76 the next, with no way to explain
the difference. `orchestrator/scoring.py` instead computes the score from numbers that
are already deterministic outputs of earlier agents (bug count, smell count, Radon's
maintainability index). Two runs on the same file produce the exact same score, and —
just as importantly — every component of the score can be traced back to a concrete,
inspectable number. That traceability felt non-negotiable for anything used to
evaluate someone's work.

---

## 6. Multi-language support

This started as a Python-only tool (the static-analysis stack — Pylint, Bandit, Radon,
the `ast` module — is Python-specific), and later grew to accept any language.

`tools/language_detect.py` does detection in three passes, each a fallback for the one
before it:

1. **Extension mapping** — a dictionary covering 60+ languages and file types (`.py` →
   python, `.js`/`.jsx` → javascript, `.java` → java, `.rs` → rust, `.hs` → haskell,
   `.ex`/`.exs` → elixir, `.clj` → clojure, `.jl` → julia, `.zig` → zig, and so on). This
   is the primary, reliable signal.
2. **Well-known extensionless filenames** — `Dockerfile`, `Makefile`, `Rakefile`,
   `Gemfile`, `CMakeLists.txt`, matched case-insensitively on the base filename.
3. **Content heuristics** — a fallback for anything still unmatched (pasted snippets,
   renamed files), using regex patterns tuned per language (`public class` +
   `System.out.println` → Java; `fn \w+\(` + `let mut` → Rust; `<?php` → PHP;
   `defmodule` → Elixir; and so on). Order matters here — Elixir's `def ... do` reads
   as valid to the generic Ruby `def ... end` pattern, so the more specific `defmodule`
   check has to run first, or Elixir source gets silently misclassified as Ruby (a real
   bug caught while writing the test suite for this module).

If none of the three passes match, detection honestly returns `"unknown"` rather than
guessing. That case gets special handling: early on, `"unknown"` was substituted
directly into agent prompts (*"you are an expert in unknown"*), which visibly degraded
output quality. `describe_language()` fixes this — when the language is `"unknown"`,
every generic-path prompt instead asks the model to **identify the language itself
from the code before analyzing it**, rather than being told a nonsense language name.

Every agent has two code paths:

- **`_run_python(...)`** — the full deterministic-tools-plus-LLM pipeline described above.
- **`_run_generic(code, language)`** — no Pylint/Bandit/Radon/ast equivalent exists for
  this language here, so a single LLM prompt does the whole job, explicitly told which
  language it's looking at and asked to return the *same JSON shape* the Python path
  would produce. This is what keeps the orchestrator, scoring, and UI completely
  language-agnostic downstream — they only ever see the common schema, never which path
  produced it.

For test generation specifically, the generic path maps each language to its idiomatic
test framework (Jest for JS/TS, JUnit 5 for Java/Kotlin, xUnit for C#, RSpec for Ruby,
PHPUnit for PHP, Catch2 for C++, `#[test]` for Rust, XCTest for Swift, etc.) so the
generated tests actually look like something a developer in that ecosystem would write,
rather than generic pseudocode. Since there's no `ast.parse()` equivalent available for
arbitrary languages here, generated non-Python tests only get a lightweight
brace-balance sanity check instead of a real syntax validation — a known, accepted gap
compared to the Python path.

`is_fully_supported(language)` exposes this distinction to the UI, which is upfront
with the user about it: "dedicated static analysis" for Python, "LLM-only analysis"
for everything else. I didn't want to quietly pretend the two paths are equivalent when
they aren't.

---

## 7. The LLM client: treating model output as untrusted input

`llm/ollama_client.py` is a thin wrapper, but it earns its place because **LLM output
is not a trustworthy data source by default**, even when you explicitly instruct
"respond with JSON only." In practice, Qwen2.5-Coder would sometimes:

- Wrap the JSON in a ` ```json ... ``` ` fence anyway
- Prepend a sentence like "Here's the analysis:" before the JSON
- Occasionally emit almost-valid JSON with a trailing comma or similar

`_extract_json()` handles the first two cases by locating the first `{`/`[` character
(after stripping a markdown fence if present) and doing a manual brace-depth scan to
find the matching close, rather than assuming `response.strip()` is directly parseable.
`generate_json()` wraps this in a retry loop (2 attempts by default) before giving up
and raising, which callers (the agents) catch and handle with their own fallback logic.

The temperature is set low (0.1) for all structured-JSON calls specifically to reduce
output variance — this isn't a creative-writing task, it's closer to structured
extraction, and lower temperature measurably reduced the rate of malformed JSON during
testing.

---

## 8. Tools layer

- **`tools/static_analysis.py`** — Pylint and Bandit are invoked as subprocesses with
  `--output-format=json` / `-f json` (they don't expose a stable importable Python API);
  Radon is used as a library directly (`cc_visit`, `mi_visit`, `h_visit`) since its
  programmatic API is stable and skips a subprocess round-trip entirely.
- **`tools/ast_parser.py`** — everything Radon and Pylint don't already cover: function
  extraction, long-function detection, god-class detection, magic-number detection,
  duplicate-block detection (via `difflib`), and naming-convention checks. This is
  100% deterministic Python — no LLM involved in detection, only in the optional
  refinement pass in `agents/code_smell.py`.
- **`tools/pdf_generator.py`** — builds the exportable PDF report with **FPDF2** and a
  Matplotlib bar chart (rendered to PNG in memory, no disk write). Two fixes worth
  documenting here:
  - The initial version used the core "Helvetica" font, which only supports Latin-1 —
    any em dash, curly quote, or emoji in LLM-generated text would crash the export
    with `FPDFUnicodeEncodingException`. Fixed by loading **DejaVu Sans** (bundled with
    matplotlib, so no new dependency) via `add_font()` instead, which covers a much
    wider Unicode range.
  - Section 4 of the PDF (the pedagogical report) originally dumped the ReportWriter
    agent's raw Markdown straight into a plain `multi_cell()` call, so the exported PDF
    literally showed `# Synthese` and `**30.1/100**` — the hashtags and asterisks
    themselves, unrendered. `markdown_body()` now does minimal line-based Markdown
    rendering (headings, `**bold**` spans, bullet lists) instead. Writing it surfaced a
    second, independent bug: fpdf2's `multi_cell()` defaults to `new_x=XPos.RIGHT`, so
    after rendering one bullet the cursor was left at the page's right edge instead of
    the left margin, and the *next* `multi_cell()` call — the next bullet — had ~0
    width available and raised `"Not enough horizontal space to render a single
    character"`. The traceback pointed at a `•` bullet character, which looked like a
    missing-glyph problem; swapping it for a plain `-` didn't fix it, which is what
    revealed the real cause was cursor position, not the character. Fixed by passing
    `new_x=XPos.LMARGIN, new_y=YPos.NEXT` explicitly on every `multi_cell()`/`cell()`
    call in this file, rather than relying on a trailing `ln()` call elsewhere to reset
    the cursor as an incidental side effect.
- **`tools/language_detect.py`** — described in §6.

---

## 9. The Streamlit dashboard

Four pages, each an independent module exposing `render()`, wired together by `app.py`
via a dict + `st.radio()` sidebar nav:

1. **Upload** (`ui/pages/upload.py`) — accepts any file, runs language detection,
   shows the result with a dropdown to override it, and tells the user upfront whether
   the language gets dedicated static analysis or LLM-only analysis.
2. **Live Analysis** (`ui/pages/live_analysis.py`) — uses LangGraph's `stream()` API
   (`stream_mode="updates"`) combined with `st.empty()` to show each agent's completion
   as it happens, plus per-agent progress bars.
3. **Results** (`ui/pages/results.py`) — tabbed view (Bugs / Smells / Complexity /
   Tests / Report) with expandable detail cards, a Matplotlib horizontal bar chart of
   per-function complexity, and syntax-highlighted code/test display.
4. **Export** (`ui/pages/export.py`) — generates and caches the PDF in
   `st.session_state` so it isn't regenerated on every rerun, with a download button.

---

## 10. Testing

The test suite (`tests/`) deliberately targets the **deterministic** modules only —
AST heuristics, the Radon wrapper, the scoring formula, language detection — so it runs
in milliseconds with zero external dependencies (no Ollama server required). This was
a conscious boundary: LLM-dependent code paths are exercised through their documented
fallback behavior (they degrade gracefully rather than crash), so testing them doesn't
require mocking an LLM or standing up Ollama in CI. `tools/pdf_generator.py` is included
in this deterministic set too — it takes structured data and (LLM-produced) Markdown
text as plain input and never calls Ollama itself. 32 tests, all passing, covering:

- Function extraction and every smell heuristic, including malformed/syntactically
  invalid input (should never raise)
- The scoring formula's edge cases (perfect code, maximally bad code, clamping,
  missing-field defaults)
- Radon's metric output on valid code and its error path on invalid syntax
- Language detection by extension, extensionless well-known filenames, and content
  fallback, including a regression test for an Elixir/Ruby misclassification bug
  caught while writing these tests
- PDF Markdown rendering: consecutive bullets no longer crash (§8's cursor-position
  bug), and headings/bold spans are actually stripped rather than left as raw `#`/`**`
  in the exported text (verified by extracting the PDF's text layer with `pypdf`)

### 10.1 Live verification against a real Ollama server

The automated suite deliberately excludes LLM-dependent code paths, which means it
cannot catch bugs that only manifest under real model latency and real (imperfect)
model output. To close that gap, the full pipeline was run end-to-end against an
actual local Ollama server (RTX 4060, `qwen2.5-coder:7b` + `mistral:7b`) on
`data/examples/bad_code.py`. This caught two real bugs the deterministic suite
structurally could not:

1. **BugHunter silently returning zero bugs** — the 120s per-agent timeout was tripped
   by 17 sequential per-finding LLM calls (~16s each ⇒ ~280s), documented in §4's
   BugHunter section. Fixed with a thread pool; verified fix brought the same run down
   to ~77s for Phase 1 with all 17 bugs correctly returned.
2. **TestGenerator's fence-stripping missing prose-prefixed responses** — documented in
   §4's TestGenerator section. Fixed with a `re.search` instead of a prefix check.

Both fixes were re-verified against the same live server afterward: BugHunter returned
17 correctly-explained findings and the overall score dropped to 30.1/F (matching the
expected grade for a file this deliberately broken), and the PDF export was confirmed
to render real Mistral-generated French report text (accented characters, em dashes)
without hitting the Unicode font issue described in §8.

---

## 11. Key design decisions, summarized

| Decision | Reasoning |
|---|---|
| LangGraph over manual `asyncio` orchestration | Its superstep model maps directly onto the parallel/sequential phase structure; built-in graph visualization helped validate topology before wiring in real logic |
| Ollama + open-weight models over any cloud API | Hard requirement: no code ever leaves the machine, zero recurring cost, no dependency on a third party's uptime |
| Deterministic tools do detection, LLM does explanation | Never ask a model to do what a reliable tool already does better and faster; the LLM's value is in explanation, generation, and synthesis — not detection |
| Score computed by formula, not by LLM | Reproducibility: identical input must always produce an identical score, and every component must be traceable to a concrete number |
| Per-agent timeout + fallback values | A single hung or failed agent should never take down the whole analysis |
| Every LLM JSON response treated as untrusted | Models don't always follow "JSON only" instructions perfectly; extraction and retry logic live in one place instead of being duplicated |
| Generated tests validated before being shown (Python) | Never present a user with broken code labeled as a working test |
| Same JSON schema for Python and non-Python paths | Keeps the orchestrator, scoring, and UI completely language-agnostic |
| Per-finding LLM calls run concurrently (BugHunter) | A live run against real Ollama showed sequential calls (~16s each) blowing past the 120s timeout on files with many findings — fixed with a small thread pool (§10.1) |

---

## 12. Known limitations

- Non-Python languages have no deterministic static-analysis layer — quality of
  detection there depends entirely on the LLM, and this is disclosed to the user
  rather than hidden.
- Generated tests for non-Python languages only get a brace-balance sanity check, not
  real syntax validation (no cheap equivalent to `ast.parse()` for arbitrary languages
  in this setup).
- No persistence layer yet — each analysis is stateless; nothing is stored between
  submissions (a SQLite-backed history was designed but not implemented — see the
  `analyses`/`issues` schema sketch that would live in a future `orchestrator` module).
- Performance is tied to local hardware: comfortable on an 8GB-VRAM GPU (~25 tok/s with
  Qwen2.5-Coder:7b), noticeably slower on CPU-only inference.
- Large files may exceed the practical context window of the 7B models, degrading
  explanation quality without any explicit chunking strategy in place yet.
