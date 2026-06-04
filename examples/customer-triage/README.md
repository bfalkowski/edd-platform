# Customer Triage Example

This example seeds a deterministic eval-driven design loop through the platform
API:

1. Create a customer triage agent design.
2. Create a failed-deployment scenario.
3. Create an eval contract with explicit pass/fail checks.
4. Run and evaluate a baseline `v0`.
5. Create a failure packet and bounded fix proposal.
6. Create a candidate `v1`.
7. Run and evaluate `v1`.
8. Compare whether the fix improved the agent.

Start the app first:

```bash
./scripts/dev.sh
```

Then seed the demo from another terminal:

```bash
python scripts/seed_customer_triage_demo.py
```

The script uses `http://127.0.0.1:8001` by default. Override it with
`EDD_PLATFORM_API_URL` if needed.
