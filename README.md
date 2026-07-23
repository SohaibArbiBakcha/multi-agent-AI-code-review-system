# 🛡️ CodeSentinel

**A multi-agent AI code review system that runs 100% locally — no API keys, no cloud, no code ever leaves your machine.**

Upload a source file in any programming language and five specialized AI agents,
orchestrated by LangGraph, analyze it in parallel/sequential phases: bugs & security
flaws, code smells, complexity metrics, generated unit tests, and a pedagogical
Markdown/PDF report — all backed by open-weight LLMs served locally through Ollama.

See [ARCHITECTURE.md](ARCHITECTURE.md) for a full technical deep-dive into how this is
built and why.

---

## ✨ Features

- 🐛 **Bug & security detection** — Pylint + Bandit for Python, LLM-driven detection for every other language, with each finding explained in plain language
- 👃 **Code smell detection** — long functions, duplicate code, god classes, magic numbers, naming issues, with refactor suggestions
- 📐 **Complexity metrics** — cyclomatic complexity, maintainability index, Halstead metrics (Radon for Python), letter grade A–F
- 🧪 **Automatic test generation** — a full test file per submission, using the idiomatic framework for the detected language (pytest, Jest, JUnit, xUnit, RSpec, PHPUnit, Catch2, and more)
- 📝 **Pedagogical reports** — a synthesized Markdown report exportable as PDF
- 🌐 **Any programming language** — auto-detected by extension with a content-based fallback; Python gets a dedicated static-analysis layer, every other language is handled by the LLM directly
- 🎯 **Transparent scoring** — a single 0–100 score with a fully auditable, reproducible formula (not another opaque LLM call)
- 🔒 **100% local** — Ollama + open-weight models (Qwen2.5-Coder, Mistral); nothing is ever sent to an external API
- ⚡ **Live progress** — streamed analysis with per-agent progress in the dashboard

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│         Streamlit Dashboard (4 pages)        │
└──────────────────────┬───────────────────────┘
                        │
┌──────────────────────▼───────────────────────┐
│      LangGraph Orchestrator (3 phases)        │
└──────────────────────┬───────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   BugHunter        CodeSmell       Complexity     ← Phase 1 (parallel)
        └───────────────┼───────────────┘
                         ▼
                  TestGenerator                    ← Phase 2
                         ▼
                  ReportWriter                      ← Phase 3
```

- **Phase 1 (parallel):** BugHunter, CodeSmell and Complexity all read the raw source
  independently, so LangGraph runs them concurrently.
- **Phase 2 (sequential):** TestGenerator consumes the function list extracted during
  Phase 1.
- **Phase 3 (sequential):** ReportWriter aggregates everything into the final report.

Every agent is timeout-protected (120s default) and degrades gracefully — a stuck or
failed agent never blocks the rest of the pipeline.

Full breakdown of every module, every design decision, and the reasoning behind each
one: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## 🚀 Quick start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running

### 1. Clone and install

```bash
git clone <this-repo-url>
cd CodeSentinel

python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 2. Pull the local models

```bash
ollama pull qwen2.5-coder:7b
ollama pull mistral:7b
ollama serve
```

### 3. (Optional) configure

```bash
cp .env.example .env
```

Override the default model names, Ollama host, or per-agent timeout in `.env` if
needed.

### 4. Run

```bash
streamlit run app.py
```

Open `http://localhost:8501`, upload a source file (try the samples in
`data/examples/`), confirm/override the detected language, and launch the analysis.

---

## 🧪 Testing

```bash
pytest tests/ -v
```

The suite covers every deterministic module (AST heuristics, the Radon wrapper, the
scoring formula, language detection, PDF export) — **32 tests, no Ollama required.** LLM-dependent
agents are exercised through their documented fallback behavior instead of requiring a
live model server in CI. Beyond the automated suite, the full pipeline has also been
run end-to-end against a real local Ollama server — see
[ARCHITECTURE.md § 10.1](ARCHITECTURE.md#101-live-verification-against-a-real-ollama-server)
for what that caught and fixed.

---

## 📁 Project structure

```
CodeSentinel/
├── app.py                    # Streamlit entrypoint
├── requirements.txt
├── .env.example
├── orchestrator/
│   ├── graph.py               # LangGraph pipeline definition
│   ├── state.py                # Shared TypedDict state
│   └── scoring.py              # Weighted scoring formula
├── agents/
│   ├── bug_hunter.py           # Agent 1 — bugs & security
│   ├── code_smell.py           # Agent 2 — code smells
│   ├── complexity.py           # Agent 3 — complexity metrics
│   ├── test_generator.py       # Agent 4 — test generation
│   └── report_writer.py        # Agent 5 — report synthesis
├── tools/
│   ├── static_analysis.py      # Pylint / Bandit / Radon wrappers
│   ├── ast_parser.py            # AST-based smell heuristics
│   ├── pdf_generator.py         # PDF report export (FPDF2 + Matplotlib)
│   └── language_detect.py       # Language detection (extension + content)
├── llm/
│   └── ollama_client.py         # Ollama client, JSON extraction & retry
├── ui/pages/
│   ├── upload.py                # Page 1 — file upload & language confirm
│   ├── live_analysis.py         # Page 2 — streamed live analysis
│   ├── results.py               # Page 3 — tabbed results dashboard
│   └── export.py                # Page 4 — PDF export
├── data/examples/               # Sample files (good/medium/bad quality)
└── tests/                       # pytest suite (deterministic modules)
```

---

## 🌐 Language support

| | Python | Other languages |
|---|---|---|
| Bug/security detection | Pylint + Bandit + LLM explanation | LLM-only detection |
| Code smells | AST heuristics + LLM refinement | LLM-only detection |
| Complexity | Radon (real metrics) | LLM estimate |
| Test generation | AST-validated pytest | LLM-generated, idiomatic framework per language |

Detection covers 60+ languages/file types by extension (including Haskell, Elixir,
Clojure, Julia, Zig, Rust, Go, Kotlin, Scala, and extensionless files like `Dockerfile`
and `Makefile`), with content-based heuristics as a fallback for anything unrecognized.
If detection genuinely can't tell, the LLM is asked to identify the language itself
from the code rather than being fed a bogus language name. The dashboard tells you
upfront which path your file will take. See
[ARCHITECTURE.md § 6](ARCHITECTURE.md#6-multi-language-support) for the full rationale.

---

## 🛠️ Tech stack

- **Orchestration:** [LangGraph](https://github.com/langchain-ai/langgraph), [LangChain](https://github.com/langchain-ai/langchain)
- **LLMs:** [Ollama](https://github.com/ollama/ollama) serving Qwen2.5-Coder:7b and Mistral:7b
- **Static analysis:** [Pylint](https://github.com/PyCQA/pylint), [Bandit](https://github.com/PyCQA/bandit), [Radon](https://github.com/rubik/radon)
- **UI:** [Streamlit](https://github.com/streamlit/streamlit)
- **PDF/charts:** [FPDF2](https://github.com/py-pdf/fpdf2), [Matplotlib](https://github.com/matplotlib/matplotlib)
- **Testing:** [pytest](https://github.com/pytest-dev/pytest)

---

## ⚠️ Known limitations

- Non-Python languages rely entirely on the LLM for detection — there's no deterministic
  static-analysis layer equivalent to Pylint/Bandit/Radon wired up for them yet.
- No persistence layer — each analysis is stateless between submissions.
- Best performance requires a GPU with ≥8GB VRAM; CPU-only inference works but is slower.
- Very large files may exceed the practical context window of the 7B models.

See [ARCHITECTURE.md § 12](ARCHITECTURE.md#12-known-limitations) for the full list.

---

## 📄 License

MIT — see [LICENSE](LICENSE).
