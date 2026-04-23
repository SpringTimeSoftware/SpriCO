# Landing Page Design

## Purpose

The SpriCO landing page is the product entry point for audit, scanner, policy, evidence, and dashboard workflows. It positions SpriCO as a domain-aware AI audit and red-teaming platform for regulated AI systems, with healthcare as one strong example rather than the only supported domain.

## Visual Approach

The page uses original React, CSS, and inline SVG visuals:

- animated AI-security pipeline showing input streams, evidence, domain signals, `PolicyDecisionEngine`, and PASS/WARN/FAIL outputs
- moving signal packets and subtle policy shield pulse
- CSS/SVG threat-card micro-animations
- responsive glass-style cards, grid textures, and original geometric flow lines

The animation supports `prefers-reduced-motion`; movement stops while the diagram remains visible.

## Layout Rules

The landing page uses a full-width product layout rather than a small centered island:

- hero container: `min(1440px, calc(100vw - 64px))`
- supporting sections: broad 1360px containers and full-width section bands where useful
- two-column desktop hero with copy on the left and animated AI audit visual on the right
- stacked tablet/mobile layout with no horizontal page scrolling
- polished cards and purposeful grid/mesh backgrounds only where they support the product story

The landing view must not render the compact left rail. For `currentView` `landing`, SpriCO shows the grouped top navigation only. Workspace views may keep the compact quick-access rail.

## Domain-Aware Positioning

The domain-aware scoring section covers:

- Healthcare AI
- Legal AI
- HR AI
- Financial AI
- Enterprise AI
- General AI Safety

These cards connect landing-page product language to policy packs and Custom Conditions. Each domain describes the kinds of signals, authorization context, sensitivity, and policy boundaries that SpriCO can evaluate.

Healthcare examples remain in a subsection titled `Healthcare example: patient-linked data risk`. The examples are synthetic and do not include real patient names, real patient IDs, real addresses, or copied transcript data.

## Sections

1. Hero with headline, subtitle, CTAs, and animated AI-security visual.
2. Trust strip with product claims, no fake metrics.
3. How SpriCO works, mapping the five-step audit flow.
4. Threat categories with micro-animations.
5. Domain-aware scoring for multiple high-risk workflows.
6. Architecture diagram showing attack engines, evidence engines, SpriCO Core, and outputs.
7. Product modules linking to existing views.
8. Final CTA.

## CTA Mappings

- `Start Interactive Audit` -> `chat`
- `Run LLM Vulnerability Scanner` -> `garak-scanner`
- `Launch Red Team Campaign` -> `red`
- `Review Evidence Center` -> `evidence`
- `Open Audit Workbench` -> `chat`
- `Configure Policies` -> `policy`
- `View Evidence Center` -> `evidence`

## Asset And License Rules

The landing page uses no external images, no stock photos, no downloaded media, and no third-party vendor screenshots. Visuals are built from original CSS, inline SVG, and existing Fluent UI components/icons already available in the repo.

No third-party vendor assets, designs, wording, screenshots, diagrams, animations, gradients, or branding are copied.

No external images are used.

## Product Safety Copy

The page states that external engines provide attack/evidence signals and SpriCO produces the final policy-aware verdict. It does not present garak, DeepTeam, promptfoo, PyRIT scorers, or optional judge output as final verdict engines.
