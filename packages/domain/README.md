# packages/domain

Shared EDD product schemas and object definitions.

This package should define canonical product language used by the API, runner,
and UI.

Current terms:

- `ProjectRecord`: the product workspace that owns designs and evidence
- `AgentDesignRecord`: the platform-owned design object created from intent
- `ArtifactRecord`: a project-scoped evidence artifact
- `ContextPack`: a deterministic assembled view over project evidence
- `EvidenceReference`: a pointer to run, eval, trace, judge, or gate evidence
