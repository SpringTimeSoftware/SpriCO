# Judge Models

SpriCO treats judge models as optional evidence sources. They are not final verdict engines.

## OpenAI Judge Status

The backend exposes:

- `GET /api/judge/status`

Default status is disabled and not configured unless backend environment variables are present.

Suggested backend configuration:

- `SPRICO_OPENAI_JUDGE_ENABLED=true`
- `SPRICO_OPENAI_JUDGE_MODEL=<approved model>`
- `OPENAI_API_KEY=<backend secret>`

API keys must be configured through backend secrets or environment configuration. They must not be entered, stored, or passed through frontend state.

## Safety Rules

- OpenAI Judge is disabled by default.
- OpenAI Judge output is evidence only.
- SpriCO PolicyDecisionEngine remains the final verdict authority.
- PHI, PII, hospital, patient, or regulated audit data must not be sent to external APIs by default.
- Healthcare/hospital workflows require redacted judge mode by default.
- Raw external judge mode is blocked unless backend/admin policy explicitly allows it.

## Scanner Request Settings

Scanner APIs may accept:

```json
{
  "judge_settings": {
    "enabled": false,
    "provider": "openai",
    "mode": "redacted",
    "judge_only_ambiguous": true
  }
}
```

If `enabled=false`, no judge action is taken.

If `enabled=true`, the backend validates that:

- the provider is configured and enabled in backend configuration;
- the selected mode is allowed;
- regulated-domain scans use redacted mode by default.

Validation failures do not create Evidence Center records or Findings.

## UI Behavior

The LLM Vulnerability Scanner shows OpenAI Judge as:

- `Not configured` when backend secrets are absent;
- `Configured, disabled by default` when backend policy enables it.

The scanner UI does not show an API key input. It links users to Settings -> Judge Models for backend configuration instructions.
