# Sentiment Observer Example

This example uses the default `Sentiment Observer` agent to demonstrate a
conversation-monitoring workflow:

1. Start from a prior customer/support exchange.
2. Run the observer against the latest customer turn.
3. Score the output with a live rubric judge.
4. Inspect the platform evidence and linked Langfuse trace.

The seeded scenario keeps the task focused on the observer job:

```text
Customer: My deployment failed after the release.
Agent: What error are you seeing?
Customer: The rollout says image pull backoff.
```

The rubric expects observer-style output, not a support-agent reply. A good
result should notice the latest turn, identify that sentiment or escalation risk
is worsening, mention the `image pull backoff` blocker, avoid claiming the issue
is fixed, and produce concise downstream-safe observer notes.

Start the app first:

```bash
./scripts/dev.sh
```

Seed the example test case:

```bash
python scripts/seed_sentiment_observer_demo.py
```

If `OPENAI_API_KEY` is available, the script also runs and live-judges the
example. To force seed-only mode:

```bash
EDD_SENTIMENT_OBSERVER_DEMO_RUN=seed python scripts/seed_sentiment_observer_demo.py
```

To force the live run and judge path:

```bash
EDD_SENTIMENT_OBSERVER_DEMO_RUN=live python scripts/seed_sentiment_observer_demo.py
```

After a live run, open the app at `http://localhost:5173`, select Sentiment
Observer, and inspect Proof loop and Evidence. The linked Langfuse trace should
show both the agent generation and the live judge generation.
