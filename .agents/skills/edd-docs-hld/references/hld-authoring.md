# HLD Authoring

Use this reference when creating or updating an HLD.

## Required Shape

An HLD should explain:

- problem;
- goals;
- non-goals;
- product model;
- architecture;
- API or data model impact;
- UI impact when relevant;
- evidence/artifact impact;
- implementation phases;
- risks;
- success criteria.

## EDD Language

Prefer these terms:

- agent design;
- agent version;
- scenario;
- eval contract;
- run evidence;
- judge output;
- failure packet;
- fix proposal;
- comparison;
- gate decision;
- trace reference;
- context pack.

Avoid older or ambiguous terms:

- local draft as a canonical platform concept;
- memory when evidence context is meant;
- Lab UI as the product frontend;
- Langfuse as source of truth.

## Review Checklist

- Does the HLD map to the product spine?
- Does it name what artifacts are created or linked?
- Does it keep CI deterministic?
- Does it distinguish deterministic checks from live LLM behavior?
- Does it describe how a user can inspect evidence?
- Does it avoid private context and portfolio-unfriendly language?
