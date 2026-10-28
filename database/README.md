# Database

The application persists data either as local JSON files (default) or in a Supabase
Postgres database. The backend selects Postgres when `SUPABASE_URL` and
`SUPABASE_SECRET_KEY` are set (`backend/ayun_db.py`); otherwise it uses the JSON stores
under `backend/data/`.

## 1. Schema

| Table | Contents |
|---|---|
| `members` | Pseudonymised members, linked to the archive import |
| `assessments` | Assessment snapshots: inputs, ratings, training zones and triggered rules |
| `expert_reviews` | Clinician sign-off on reviewed plans |
| `knowledge_nodes` | Clinician-validated knowledge used to ground LLM answers |
| `expert_tickets` | Member questions routed to experts |
| `app_users` | Member accounts |
| `member_memory` | Consent-gated episodic conversation summaries |
| `ask_history` | Saved Ask Joule questions and answers |
| `ayun_import_batches`, `ayun_import_rows` | Bulk imports of historical, pseudonymised data |

Row-level security is enabled with deny-all policies for anonymous and authenticated
clients; only the server, using the secret key, reads and writes.

## 2. Setup

1. Create a Supabase project.
2. Run the migrations in `migrations/` in numerical order (`001` to `006`) in the SQL editor.
3. Set `SUPABASE_URL` and `SUPABASE_SECRET_KEY` (the secret key, not the publishable key)
   in `.env` or the hosting platform, and restart the application.

## 3. Demo cases

`demo/` contains four fictional members (users, assessments, tickets and one knowledge
node). They are seeded automatically into empty JSON stores by `backend/data_paths.py`.
To load them into Postgres:

```bash
python database/scripts/seed_demo_cases.py
```

The demo accounts use the password in `DEFAULT_MEMBER_PASSWORD` (default `ayun123456`).

## 4. Historical data import

`scripts/import_ayun_archive.py` imports a pseudonymised Excel export. Multi-level headers
are flattened to `Category::Parameter` keys, matching the parameter names used by the
rule engine.

```bash
python database/scripts/import_ayun_archive.py export.xlsx \
  --batch-name "clinic_archive" --pseudonym-column "anonymous_token" --imported-by "name"
```

## 5. Limitations

The schema serves a research prototype. A clinical deployment would require member-scoped
access policies, a data processing agreement with the hosting providers and a review of
retention periods.
