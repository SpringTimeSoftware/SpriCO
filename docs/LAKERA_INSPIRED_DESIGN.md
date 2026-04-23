# Lakera-Inspired SpriCO Design

SpriCO implements Lakera-inspired product patterns natively. It does not copy Lakera proprietary detector internals and does not use Lakera as a final verdict engine.

Implemented native surfaces:

- Shield runtime check: `POST /api/shield/check`
- Projects: `/api/projects`
- Policies: `/api/policies`
- Policy simulation: `POST /api/policies/{policy_id}/simulate`
- Red objective library and scans: `/api/red/*`
- Runtime evidence log: `GET /api/evidence`

Shield flow:

1. Accept OpenAI-style messages.
2. Screen latest interaction while using history as context.
3. Emit `SensitiveSignal` objects from prompt defense, DLP, PHI, secrets, moderation, link, custom detector, RAG/tool checks.
4. Build authorization context from SpriCO metadata only.
5. Run `PolicyDecisionEngine`.
6. Return allow, warn, block, mask, or escalate with breakdown and optional payload.

Red flow:

1. Select target and recon context.
2. Select baseline or domain objectives.
3. Store scan lifecycle record.
4. Compare scans by risk summary and finding deltas.

Current limitations:

- Red scan execution is scaffolded; objective execution strategies are not yet running adversarial conversations.
- Policy and project persistence is JSON-backed to avoid disruptive schema migration.
- Enterprise RBAC, SIEM export, region enforcement, and retention enforcement are represented in policy fields but not fully enforced.
