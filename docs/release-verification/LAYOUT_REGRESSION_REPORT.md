# Layout Regression Report

## Scope

This pass targeted the authenticated desktop workspace width regression reported in local builds.

The goal was not to redesign the landing page. The goal was to restore normal desktop width usage for authenticated pages and verify that the workspace no longer renders as a narrow centered island.

## Reproduction

Reproduced locally: yes.

Observed symptom:

- Interactive Audit looked visually capped to a narrow centered column on desktop.
- The composer and the message lane left large unused side areas.
- The issue was most obvious in the empty-state / pre-message view and in any short transcript.

Reference before-fix screenshot:

- `docs/release-verification/screenshots/local/02-interactive-audit-top.png`

## Exact Root Cause

The root cause was **not** the authenticated shell in `MainLayout`.

The shell was already stretching correctly:

- `frontend/src/components/Layout/MainLayout.styles.ts`
  - `contentArea.width = 100%`
  - `main.flex = 1`
  - `main.width = 100%`

The actual width caps were inside the Interactive Audit workspace:

1. `frontend/src/components/Chat/ChatInputArea.styles.ts`
   - `inputContainer.maxWidth = '900px'`
   - `inputContainer.margin = '0 auto'`

2. `frontend/src/components/Chat/MessageList.styles.ts`
   - `message.maxWidth = '800px'`

Those two rules made the authenticated chat experience look like a narrow centered island even though the parent layout was already full width.

## Pages Affected

Directly affected:

- Interactive Audit
- Saved Interactive Audit replay view

Verified not to share the same root cause:

- LLM Vulnerability Scanner
- Structured Dashboard
- Other `sprico-shell` / `audit-platform` workspace pages that already filled the available shell width

## Minimal Fix Applied

Files changed:

- `frontend/src/components/Chat/chatLayout.constants.ts`
- `frontend/src/components/Chat/ChatInputArea.styles.ts`
- `frontend/src/components/Chat/MessageList.styles.ts`

Changes:

1. Added shared width guard constants for the Interactive Audit workspace.
2. Increased composer width from `900px` to `1400px` max while keeping `width: 100%`.
3. Increased message lane width from `800px` max to `min(1280px, 92%)`.

This keeps the landing page untouched and avoids changing the global shell.

## Before / After Notes

Before:

- Interactive Audit visually read as a narrow centered lane.
- The desktop shell had large unused left/right space.
- The issue looked like a global shell problem, but it was actually caused by internal chat max-width rules.

After:

- The composer now spans the available workspace width appropriately on desktop.
- The message lane is wide enough to read as part of the full workspace rather than a centered island.
- The rest of the authenticated shell remains unchanged.
- No horizontal overflow was observed in the local verification captures.

## Verification Screenshots

Post-fix local screenshots saved to:

- `docs/release-verification/layout-verification/interactive-audit-layout.png`
- `docs/release-verification/layout-verification/llm-vulnerability-scanner-layout.png`
- `docs/release-verification/layout-verification/structured-dashboard-layout.png`

Interpretation:

- `interactive-audit-layout.png`: confirms the width regression fix in the affected page.
- `llm-vulnerability-scanner-layout.png`: confirms other authenticated workspace pages still use width correctly.
- `structured-dashboard-layout.png`: confirms dashboard layout remains full-width and readable after the chat-only fix.

## Result

Status: fixed locally.

The authenticated width regression was real, but it was localized to the Interactive Audit message/composer constraints rather than the main authenticated shell.
