# Customer Triage Example

This example seeds a live eval-driven design loop through the platform API:

1. Create a customer triage agent design.
2. Create a failed-deployment scenario.
3. Create an eval contract with two checks: a live judge decides whether the
   answer asks for deployment logs without guessing at a cause, and a
   deterministic check fails it if it says "refund approved".
4. Run baseline `v0` live against Anthropic and have the live judge evaluate it.
5. Create a fix proposal from `v0`'s failure packets.
6. Create a candidate `v1` that asks for logs and does not guess at a cause.
7. Run `v1` live and have the live judge evaluate it.
8. Compare whether the fix improved the agent.

The script makes live, billed Anthropic calls: two agent runs and two judge
calls each time you run it, about a minute and a half in all. Each run creates
a new agent; it does not reuse an earlier one. Because the answers are live,
the scores can differ from run to run. A typical result is `v0` 1/2, `v1` 2/2,
and one fixed failure packet.

The API needs `ANTHROPIC_API_KEY`. Put it in `.env.local` before you start the
app:

```bash
./scripts/dev.sh
```

Then seed the demo from another terminal:

```bash
python scripts/seed_customer_triage_demo.py
```

If the API has no Anthropic key, the script stops before creating anything and
says so. It prints the agent ID, the run mode and provider, both scores, and the
comparison summary.

The script uses `http://127.0.0.1:8001` by default. Override it with
`EDD_PLATFORM_API_URL` if needed.
