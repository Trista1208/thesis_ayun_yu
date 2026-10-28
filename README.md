# A Data-Driven Sport-Related Health Recommendation System for Longevity Center AYUN

**Combining Rule-Based Expert Systems with LLMs for Personalised Exercise and Health Prescription**

Master's thesis software artefact · Author: Jiaqi Yu

## Where to start

The demonstration to review is [`web/`](web/). The method is [`knowledge/`](knowledge/), [`backend/rules/`](backend/rules/), and [`backend/ai/`](backend/ai/), with the saved evaluation in [`evaluation/`](evaluation/).

Four folders are kept so the record is complete. They are not the system described in the thesis:

| Folder | What it is |
|---|---|
| [`frontend/`](frontend/) | Earlier Streamlit prototype. Open `web/` instead. |
| [`_archive/`](_archive/) | Early research scripts from before the rule engine. |
| [`deployment_history/`](deployment_history/) | Retired Railway and Fly.io configs. The live deploy is Vercel. |
| [`pitch/`](pitch/) | Interface sketches. Not part of the clinical method. |

Paths are unchanged, so Appendix D of the thesis still matches this tree.

## Abstract

This repository contains the system developed for the thesis. It translates a member's
assessment data (body composition, physiological testing, blood biomarkers and genetic
risk) into age- and sex-stratified exercise and health recommendations. A rule-based
expert system, built on a version-controlled YAML knowledge base, makes every
recommendation decision. A large language model (LLM) layer explains these decisions and
answers member questions, grounded in the rule engine's output and in clinician-validated
knowledge. Clinicians review plans and answer escalated questions, keeping a human in the
loop.

## Reading this repository with the thesis

The submitted version of the code is tagged `v1.0-thesis`. Appendix D (Code Map) of the
thesis lists the files behind each component; they are at the same paths here.

| Thesis | Component | Files |
|---|---|---|
| Ch. 3–4 | Rule base (YAML, schema 2.2) and protocol library | `knowledge/sports_health_recommendations.yml`, `knowledge/protocols_quick_reference.yml` |
| Ch. 4–5 | Rule engine and clinical rules | `backend/rules/rule_engine.py`, `backend/rules/member_signals.py` |
| Ch. 4 | Cited Q&A engine (Joule), language-model client and coach prompt | `backend/ai/ask_engine.py`, `backend/ai/chatbot.py`, `backend/ai/prompts/sports_scientist.txt` |
| Ch. 4 | Talk route, source-chip labels, Evipedia references | `api/routes/chat.py`, `web/src/lib/sources.ts`, `knowledge/evipedia_references.yml`, `backend/ai/evipedia_refs.py` |
| Ch. 5 | Deployment (Vercel) | `vercel.json`, `api/index.py`; earlier Railway and Fly.io attempts in `deployment_history/` |
| Ch. 6 | Boundary unit tests | `backend/tests/test_rule_engine.py` |
| Ch. 6 | Threshold suite and results | `evaluation/eval_threshold_suite_v2.py`, `evaluation/eval_threshold_results_v2.json` |
| Ch. 6 | Hallucination count: scripts, answers and scores | `evaluation/eval_joule_scripts.py`, `evaluation/eval_joule_answers_gemini.jsonl`, `evaluation/eval_joule_answers_qwen.jsonl`, `evaluation/eval_joule_scores.json` |

## Repository structure

| Path | Contents |
|---|---|
| `knowledge/` | YAML knowledge base: reference ranges, recommendation rules, protocols, literature references |
| `backend/rules/` | Rule-based expert system: rule engine, recommendations, training zones, protocols |
| `backend/ai/` | LLM layer: grounded question answering, knowledge corpus, member memory |
| `backend/voice/` | Voice agent (Talk mode) and text-to-speech |
| `backend/documents/` | PDF and free-text intake; report export |
| `backend/workflow/`, `backend/storage/`, `backend/auth/` | Clinician workflow, persistence and authentication |
| `backend/tests/` | Rule-engine boundary tests |
| `evaluation/` | Thesis evaluation scripts and saved results, under the same file names |
| `api/` | FastAPI service |
| `web/` | React demonstration of the member and clinician flows |
| `frontend/` | Streamlit app for sports scientists (earlier prototype; the demonstration to review is `web/`) |
| `database/` | Postgres schema and fictional demo cases |
| `docs/` | [Architecture](docs/architecture.md), [deployment](docs/deployment.md) and [evaluation](docs/evaluation.md) |
| `pitch/` | Visual directions for the interface, not part of the clinical method |
| `_archive/`, `deployment_history/` | Early research scripts and retired deployment configurations |

## Running locally

Requirements: Python 3.11 or later and Node.js 20.

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn api.main:app --reload --port 8000
```

In a second terminal, run `cd web && npm install && npm run dev` and open
http://localhost:5173. That React app is the demonstration to walk through. `frontend/`
is the earlier Streamlit prototype.

Without configuration the system uses local JSON storage and four fictional demo members.
Sign in with password `ayun123456`:

| Member | Email |
|---|---|
| Jonas Weber | `jonas.demo@ayun.local` |
| Sofia Rossi | `sofia.demo@ayun.local` |
| Marco Keller | `marco.demo@ayun.local` |
| Lena Hofmann | `lena.demo@ayun.local` |

The clinician password is set locally in `.env` as `EXPERT_PASSWORD` and is not published.
LLM features need a local Ollama instance or a Gemini API key (see `.env.example`).

## Evaluation

The rule engine's correctness tests run without network access or API keys:

```bash
pip install pytest
python -m pytest backend/tests
```

See [docs/evaluation.md](docs/evaluation.md) for the procedure and its scope.

The recorded thesis runs are in `evaluation/`, with the file names used in the thesis:

- `eval_threshold_suite_v2.py` and `eval_threshold_results_v2.json`
- `eval_joule_scripts.py`, `eval_joule_scores.json`, `eval_joule_answers_gemini.jsonl` and `eval_joule_answers_qwen.jsonl`

## Deployment

A test deployment of this repository is at [https://ayun-full.vercel.app](https://ayun-full.vercel.app).
The members there are the fictional demo cases above. The clinician password is not
published.

The application is deployed on Vercel (`vercel.json`): the React application as a static
site and the FastAPI service as a Python serverless function. See
[docs/deployment.md](docs/deployment.md).

## Use of AI

**In the system.** LLMs are used only for communication: explaining recommendations,
answering questions with cited sources and drafting replies for clinicians. The supported
models are Gemini Flash (hosted) and Qwen 2.5 via Ollama (local). ElevenLabs
provides optional speech output. Recommendation decisions are made exclusively by the
rule engine, so the same input always yields the same recommendations.

**In development.** Generative AI coding assistants were used to support implementation,
refactoring, testing and documentation of this repository. All AI-generated output was
reviewed, tested and adapted by the author, who takes full responsibility for the code and
its content. The clinical rules and reference ranges in `knowledge/` were derived from
literature and AYUN's sports-science practice and reviewed with the clinic's sports
scientists, not generated by AI.

## Data protection

The repository contains no real member data. All accounts, assessments and tickets in
`database/demo/` are fictional, and runtime data in `backend/data/` is excluded from
version control.

## Interface

The React application in `web/` demonstrates the recommendation system so that a
reader can sign in, inspect a plan and ask a question. The visual interface is not
the purpose of this project. The thesis contribution is the rule-based method, the
knowledge base and the grounded language-model layer.

The 3D body on the home page is not original work. It uses anatomical models from
BodyParts3D, published by the Database Center for Life Science. Most structures are
used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The lung
meshes are used under
[CC BY-SA 2.1 Japan](https://creativecommons.org/licenses/by-sa/2.1/jp/).
Attribution, sources and the changes made for this view are in
[`web/public/models/anatomy/NOTICE.md`](web/public/models/anatomy/NOTICE.md).
