# apps/api

FastAPI backend for EDD Platform.

This app owns persistence, agent designs, versions, scenarios, eval
contracts, runs, eval results, judge outputs, failure packets, fix
proposals, comparisons, gates, evidence artifacts/links/context packs, and
the Langfuse integration boundary.

The API surface is generated, not hand-maintained here — see
[`../../docs/API_CONTRACT.md`](../../docs/API_CONTRACT.md) and
[`../../docs/openapi.json`](../../docs/openapi.json) for the current contract
and the contract-first rules to follow before adding or changing routes.

Local state is stored in Postgres by default. The API reads
`EDD_PLATFORM_DATABASE_URL`, defaulting to
`postgresql://edd_platform:edd_platform@127.0.0.1:15432/edd_platform`.

Tests use `EDD_PLATFORM_STORAGE_BACKEND=memory` so they do not require a
database service.

Run requests default to deterministic `mock` mode (no provider credentials
required). To run live, set `ANTHROPIC_API_KEY` and send `"mode": "live"` to
the run endpoint. The default live model is Claude Haiku; override with
`EDD_ANTHROPIC_MODEL`. The console never sends `mock` — see
[`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md)'s Runtime Modes
section for the console/API boundary.
