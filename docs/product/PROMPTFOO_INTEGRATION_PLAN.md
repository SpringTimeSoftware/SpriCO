# Promptfoo Integration Plan

## Purpose

`promptfoo Runtime` is an optional external runtime adapter inside Benchmark Library.

It exists to:

- run promptfoo plugins and strategies against one or more configured SpriCO targets
- import promptfoo result rows as normalized evidence
- let SpriCO create Findings only when SpriCO's own evaluation is actionable
- keep promptfoo visible in unified runs, dashboards, and Activity History

It does **not** own final verdict authority.

Hard rule:

- promptfoo output is evidence only
- `SpriCO PolicyDecisionEngine` remains the final verdict authority

## What Promptfoo Runtime Is

Promptfoo Runtime is the execution layer for optional promptfoo-based probes inside the Benchmark Library workspace.

It supports:

- built-in promptfoo plugin groups and plugins from `/api/promptfoo/catalog`
- promptfoo strategies from `/api/promptfoo/catalog`
- one-target runs
- multi-target comparison runs
- custom policy generation through the promptfoo `policy` plugin
- custom prompt/intention generation through the promptfoo `intent` plugin

It does not expose raw shell command entry or arbitrary free-form runtime command editing.

## Plugins And Strategies

`Plugins` define what promptfoo is trying to test.

Examples:

- privacy / PII-style checks
- harmful or policy-violation probes
- custom `policy` plugin entries generated from policy text
- custom `intent` plugin entries generated from user-authored prompts

`Strategies` define how promptfoo mutates or frames the test attempts.

Examples:

- `base64`
- other installed promptfoo strategies returned by the live catalog

The UI must source selectable plugins and strategies from:

- `GET /api/promptfoo/catalog`

The catalog response includes:

- `promptfoo_version`
- `discovered_at`
- `catalog_hash`
- `plugin_groups`
- `plugins`
- `strategies`

Saved selections are validated against the current catalog. Missing items are shown as missing/disabled and are never silently remapped.

## Credential Model

Promptfoo provider credentials are configured explicitly. Supported source types are:

- `environment`
- `secret_ref`
- `target_secret_ref`
- `disabled`

Status is reported without showing secret values:

```json
{
  "provider_credentials": {
    "openai": {
      "configured": true,
      "source_type": "environment",
      "source_label": "OPENAI_API_KEY",
      "value_visible": false
    }
  }
}
```

Rules:

- promptfoo must not silently reuse a target secret unless `target_secret_ref` is explicitly configured
- secret values are never returned by `/api/promptfoo/status`
- secret values are never written into generated promptfoo configs or artifacts

## Custom Policies

Custom Policies use the promptfoo `policy` plugin.

User inputs:

- policy name
- policy text
- severity
- number of generated tests
- domain
- optional tags

Generated config shape:

```yaml
redteam:
  plugins:
    - id: policy
      numTests: 2
      severity: high
      config:
        policy: Do not reveal patient-identifying diagnosis information.
        policyName: No PHI By Name
```

Custom policy results import as evidence with promptfoo-specific metadata such as:

- `promptfoo_plugin_id = policy:<policy_id>`
- `promptfoo_policy_name`
- `promptfoo_policy_text_hash`
- `promptfoo_policy_text_redacted = true`

The raw policy text itself is not treated as a secret, but the stored evidence path keeps it redacted/hashed for safer handling.

## Custom Intents

Custom Intents use the promptfoo `intent` plugin.

User inputs:

- intent name
- prompt text
- category
- severity
- optional multi-step sequence
- optional tags

Important distinction:

- `intent` = the authored starting prompt or prompt sequence
- `policy` = the rule the target must not violate

Multi-step intent sequences run as authored. They are not automatically transformed by promptfoo strategies in the same way as single-turn inputs.

## Single-Target And Multi-Target Runs

### Single target

One target + one or more policies + one or more plugins/custom workloads + one or more strategies produces one or more `promptfoo_runtime` unified runs.

### Multi-target comparison

Two or more targets under the same plugin/strategy selection produce a comparison group.

Each target result still preserves:

- `run_id`
- `target_id`
- `policy_id`
- per-target evidence linkage
- per-target finding linkage

This allows one target to create actionable findings while another target in the same comparison group remains coverage-only.

## Evidence, Findings, Dashboard, And Activity History

Every completed promptfoo launch maps into the unified reporting model.

Expected downstream connections:

- `unified runs`
- `Activity History`
- `Evidence Center`
- `Findings` only when SpriCO says the outcome is actionable
- `dashboard coverage`

No-finding runs are still important. They appear as coverage and should not create Findings.

## Secret Hygiene

Generated artifacts must not contain:

- API keys
- bearer tokens
- raw `Authorization` headers
- decrypted target secrets
- raw provider credentials

Artifact scans distinguish between:

- real credential secret matches
- harmless token-usage/rate-limit metadata

Promptfoo is not production-ready unless:

- status is available
- a real run executes
- artifacts are created
- no credential leaks are found
- unified reporting remains intact

## Why Promptfoo Is Evidence-Only

Promptfoo can tell SpriCO that a test row passed, failed, or needs review from promptfoo's perspective.

That is still not the platform verdict.

Final authority remains inside SpriCO because:

- SpriCO must normalize evidence across multiple engines
- regulated-domain decisions must be consistent across workflows
- Findings must stay actionable-only
- dashboard and reporting logic must not depend on a single third-party runtime
