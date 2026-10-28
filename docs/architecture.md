# System Architecture

This document describes the components of the artefact and where each is implemented. It
complements the accompanying thesis. Diagrams: [`diagrams/ayun_architecture_clean.png`](diagrams/ayun_architecture_clean.png)
(system overview) and [`joule-architecture.svg`](joule-architecture.svg) (member application).

## 1. Design principles

- **Deterministic decision, probabilistic communication.** Recommendations are produced by
  a rule engine evaluating a hand-curated YAML knowledge base. The LLM layer receives the
  engine's output as context and is used for explanation, question answering and drafting.
- **Explicit knowledge.** Reference ranges, rules and protocols are stored as YAML under
  version control, so every change to clinical logic is reviewable in the commit history.
- **Human in the loop.** Clinicians review assessment plans and answer member tickets.
  Validated answers become part of a knowledge corpus that grounds later LLM responses; they
  never modify the rule engine.
- **Shared domain layer.** Both user interfaces call the same Python package, `backend/`,
  which is divided into one sub-package per layer.

## 2. Layers and components

### 2.1 Knowledge base (`knowledge/`)

| File | Role |
|---|---|
| `sports_health_recommendations.yml` | Age- and sex-stratified reference ranges and recommendation rules |
| `protocols_quick_reference.yml` | Named AYUN exercise protocols shown on plan cards |
| `evipedia_references.yml` | Curated literature references cited in answers |

`backend/ai/prompts/sports_scientist.txt` holds the system prompt for the LLM layer and
`backend/workflow/experts.yaml` the expert roster. The clinical inputs these files encode are summarised in
[`sports_scientist_checks.md`](sports_scientist_checks.md).

### 2.2 Decision layer (`backend/rules/`)

| Module | Role |
|---|---|
| `rule_engine.py` | Loads the YAML rules, rates each parameter against its stratified reference band, evaluates rule conditions and assigns priorities |
| `recommendation_api.py` | Entry point for recommendations; assembles triggered rules, ratings and target gaps into one result and LLM context |
| `training_zones.py` | Heart-rate training zones from VT1, VT2 and HRmax |
| `protocol_library.py` | Maps triggered rules to protocols from the quick reference |
| `member_signals.py` | Deterministic flags (for example injuries) the conversational layer must address |

### 2.3 Document intake and export (`backend/documents/`)

| Module | Role |
|---|---|
| `pdf_extractor.py` | Two-stage extraction from clinical PDFs (DEXA, CPET, blood panels): regular expressions followed by optional LLM extraction, merged by field priority |
| `text_intake.py` | Converts free-text notes into structured parameters |
| `report_generator.py` | PDF and Word export of plans |

### 2.4 AI layer (`backend/ai/`)

| Module | Role |
|---|---|
| `chatbot.py` | LLM client (Ollama locally; Gemini remotely) |
| `ask_engine.py` | Grounded question answering over member context and the validated corpus, with ticket routing when confidence is low |
| `expert_ticket_assistant.py` | Drafting support for clinicians answering tickets |
| `knowledge_pipeline.py`, `knowledge_search.py` | Capture clinician-validated answers as knowledge nodes and retrieve them for grounding |
| `evipedia_refs.py` | Retrieval over the literature references |
| `memory_store.py` | Consent-gated episodic memory of member conversations |

### 2.5 Voice agent (`backend/voice/`)

| Module | Role |
|---|---|
| `talk_agent.py` | Conversational "Talk" mode; proposes an expert ticket that the member must confirm |
| `elevenlabs_voice.py` | Optional server-side text-to-speech |

### 2.6 Clinician workflow (`backend/workflow/`)

| Module | Role |
|---|---|
| `experts.py`, `experts.yaml` | Expert roster and availability |
| `ticket_service.py` | Ticket creation and expert assignment |

### 2.7 Persistence (`backend/storage/`)

| Module | Role |
|---|---|
| `user_store.py`, `plan_review_store.py` | Member accounts, assessments and reviewed plans |
| `knowledge_store.py` | Knowledge nodes and expert tickets |
| `ayun_db.py` | Supabase Postgres client; used when `SUPABASE_URL` is set, otherwise JSON files |
| `data_paths.py` | Resolves the writable data directory (`backend/data/` locally, `/tmp/ayun-data` on serverless) and seeds demo cases from `database/demo/` |

### 2.8 Authentication (`backend/auth/`)

| Module | Role |
|---|---|
| `session_tokens.py` | Signed, stateless session tokens for members and experts |
| `expert_auth.py` | Password gate for the expert area |
| `google_oauth.py` | Google sign-in for members |

### 2.9 HTTP layer (`api/`)

`api/main.py` creates the FastAPI application, registers the routers under `/api` and, when
`web/dist` exists, serves the built React application from the same origin. Routers in
`api/routes/`: `auth`, `assessments`, `chat`, `tickets`, `knowledge`, `experts`, `extract`,
`reviews`, `memory`, `voice` and `health`. Request and response models are in
`api/schemas.py`.

### 2.10 User interfaces

- **`web/`** is the React application. Member pages: login, profile, assessment, plan,
  Ask Joule and tickets. Expert pages: login, member list, plan review and knowledge library.
  `web/src/lib/api.ts` is the API client.
- **`frontend/app.py`** is the Streamlit console used by sports scientists in the original
  prototype. It imports the `backend/` modules directly and does not use the API.

## 3. Data flow of an assessment

1. Parameters are entered manually or extracted from uploaded reports.
2. `backend.rules.recommendation_api.get_recommendations` rates each parameter and evaluates the rules.
3. The result (ratings, triggered recommendations, training zones, protocols) is stored as
   an assessment and shown as a draft plan.
4. A clinician reviews and publishes the plan.
5. Questions the LLM layer cannot answer with sufficient grounding become tickets; the
   clinician's validated answer is added to the knowledge corpus.
