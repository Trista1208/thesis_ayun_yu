# Runtime data

The JSON stores are written here when the application runs without Supabase. The contents
are excluded from version control because they may contain personal and health data.

| Path | Contents |
|---|---|
| `users/` | Member accounts |
| `sessions/` | Session records |
| `plan_reviews/` | Assessments and reviewed plans |
| `knowledge/` | Tickets, validated knowledge, member memory and the expert roster state |

Missing files are created on first use and seeded with the fictional cases from
`database/demo/`. Set `AYUN_DATA_DIR` to store the data elsewhere. See
[`docs/deployment.md`](../../docs/deployment.md) for persistent storage.
