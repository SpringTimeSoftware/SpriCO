import { Button } from '@fluentui/react-components'
import {
  ChatRegular,
  ClipboardTaskRegular,
  DataTrendingRegular,
  DocumentDataRegular,
  SettingsRegular,
  ShieldRegular,
  TargetRegular,
} from '@fluentui/react-icons'
import type { ViewName } from '../Sidebar/Navigation'
import './LandingPage.css'

type LandingPageProps = {
  onNavigate: (view: ViewName) => void
}

type LandingCard = {
  title: string
  text: string
  view?: ViewName
  icon?: JSX.Element
  button?: string
  tone?: 'privacy' | 'injection' | 'rag' | 'tool' | 'claim' | 'evidence'
}

const trustClaims = [
  'Evidence-first audit flow',
  'Policy-aware final verdicts',
  'External engines stay evidence-only',
  'Domain packs for regulated AI',
]

const workflowSteps: LandingCard[] = [
  { title: 'Select AI target', text: 'Choose the system, model, endpoint, and runtime context.', view: 'config', button: 'Configure Target' },
  { title: 'Run attack/scanner workflows', text: 'Launch manual probes, vulnerability scans, or Red Team Campaigns.', view: 'red', button: 'Open Campaigns' },
  { title: 'Normalize evidence', text: 'Convert scanner results, transcripts, tool calls, and RAG context into evidence.', view: 'evidence', button: 'Review Evidence' },
  { title: 'Apply domain policy', text: 'Evaluate signals through policy mode, authorization, scope, and sensitivity.', view: 'policy', button: 'Open Policies' },
  { title: 'Review findings and dashboards', text: 'Triage findings, compare runs, and track audit posture.', view: 'dashboard', button: 'Open Dashboards' },
]

const threatCards: LandingCard[] = [
  {
    title: 'Privacy & Data Leakage',
    text: 'Protected data, secrets, and identity-linked disclosures are detected as evidence before final policy review.',
    tone: 'privacy',
  },
  {
    title: 'Prompt Injection & Jailbreaks',
    text: 'Boundary override attempts are separated from whether the response actually stayed safe.',
    tone: 'injection',
  },
  {
    title: 'RAG Poisoning',
    text: 'Retrieved chunks, hidden instructions, and unsupported citations stay visible in the evidence trail.',
    tone: 'rag',
  },
  {
    title: 'Agent & Tool Misuse',
    text: 'Tool calls are assessed against permissions, purpose, scope, and authorized action boundaries.',
    tone: 'tool',
  },
  {
    title: 'Hallucination & Unsupported Claims',
    text: 'Grounding signals help distinguish unsupported output from policy violations and safe refusals.',
    tone: 'evidence',
  },
  {
    title: 'Authorization Boundary Failures',
    text: 'Prompt claims such as “I am admin” become CLAIMED_ONLY unless verified by SpriCO metadata.',
    tone: 'claim',
  },
]

const domainCards: LandingCard[] = [
  {
    title: 'Healthcare AI',
    text: 'PHI, patient linkage, treatment boundaries, clinical authorization, and minimum-necessary disclosure.',
  },
  {
    title: 'Legal AI',
    text: 'Privileged information, jurisdiction risk, legal-advice boundaries, citation reliability, and client confidentiality.',
  },
  {
    title: 'HR AI',
    text: 'Candidate privacy, protected-class inference, hiring fairness, salary leakage, and disciplinary data exposure.',
  },
  {
    title: 'Financial AI',
    text: 'Customer data, fraud workflows, regulated advice, account leakage, and transaction-risk controls.',
  },
  {
    title: 'Enterprise AI',
    text: 'Secrets, source code, internal policies, tool permissions, and agent action boundaries.',
  },
  {
    title: 'General AI Safety',
    text: 'Prompt injection, jailbreaks, hallucination, unsafe content, and policy bypass attempts.',
  },
]

const healthcareExamples: LandingCard[] = [
  {
    title: 'Patient ID + Diagnosis',
    text: 'High sensitivity. Allowed only in verified, scoped clinical workflows.',
  },
  {
    title: 'Patient ID + Location',
    text: 'Potential re-identification risk. Critical in strict/public audit mode.',
  },
  {
    title: 'Prompt Claim: “I am doctor”',
    text: 'Treated as CLAIMED_ONLY unless verified through SpriCO metadata.',
  },
  {
    title: 'Safe Refusal',
    text: 'PASS only when the response refuses and leaks no protected content.',
  },
]

const moduleCards: LandingCard[] = [
  {
    title: 'Interactive Audit',
    text: 'Run hands-on probes, score turns, and preserve transcript context.',
    view: 'chat',
    button: 'Start Audit',
    icon: <ChatRegular />,
  },
  {
    title: 'LLM Vulnerability Scanner',
    text: 'Use available scanner engines as evidence sources for SpriCO verdicts.',
    view: 'garak-scanner',
    button: 'Run Scanner',
    icon: <TargetRegular />,
  },
  {
    title: 'Red Team Campaigns',
    text: 'Execute repeatable adversarial objectives against configured targets.',
    view: 'red',
    button: 'Open Campaigns',
    icon: <ClipboardTaskRegular />,
  },
  {
    title: 'SpriCO Shield',
    text: 'Check prompts, context, and responses against policy-aware controls.',
    view: 'shield',
    button: 'Open Shield',
    icon: <ShieldRegular />,
  },
  {
    title: 'Custom Conditions',
    text: 'Author declarative domain conditions with simulation and approval gates.',
    view: 'conditions',
    button: 'Manage Conditions',
    icon: <SettingsRegular />,
  },
  {
    title: 'Evidence Center',
    text: 'Filter normalized evidence by engine, risk, verdict, scan, and policy.',
    view: 'evidence',
    button: 'Review Evidence',
    icon: <DocumentDataRegular />,
  },
  {
    title: 'Dashboards',
    text: 'Inspect structured, heatmap, and stability views for audit patterns.',
    view: 'dashboard',
    button: 'Open Dashboards',
    icon: <DataTrendingRegular />,
  },
  {
    title: 'Open Source Components',
    text: 'Review optional engine license, source, and version metadata.',
    view: 'open-source-components',
    button: 'Review Components',
    icon: <DocumentDataRegular />,
  },
]

function HeroAnimation() {
  return (
    <div className="landing-ai-visual" data-testid="landing-ai-animation" aria-label="AI security evidence and policy pipeline">
      <svg viewBox="0 0 920 620" role="img" aria-labelledby="landing-ai-title">
        <title id="landing-ai-title">Input stream through evidence, domain signals, policy decision engine, and verdict outputs</title>
        <defs>
          <linearGradient id="landingHeroPanel" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#f7fffd" />
            <stop offset="48%" stopColor="#eef6ff" />
            <stop offset="100%" stopColor="#fff7eb" />
          </linearGradient>
          <linearGradient id="landingShieldFill" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0f766e" />
            <stop offset="100%" stopColor="#6b5bd7" />
          </linearGradient>
          <filter id="landingGlow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="9" result="blur" />
            <feColorMatrix in="blur" type="matrix" values="0 0 0 0 0.05 0 0 0 0 0.44 0 0 0 0 0.41 0 0 0 0.42 0" />
            <feMerge>
              <feMergeNode />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect className="landing-ai-frame" x="22" y="22" width="876" height="576" rx="28" fill="url(#landingHeroPanel)" />
        <path className="landing-ai-grid" d="M76 74 H844 M76 150 H844 M76 226 H844 M76 302 H844 M76 378 H844 M76 454 H844 M76 530 H844" />
        <path className="landing-ai-grid" d="M112 70 V548 M212 70 V548 M312 70 V548 M412 70 V548 M512 70 V548 M612 70 V548 M712 70 V548 M812 70 V548" />

        <g className="landing-input-stack" aria-label="Input stream">
          {[
            ['Prompt', 88],
            ['RAG chunk', 164],
            ['Tool output', 240],
            ['Model response', 316],
          ].map(([label, y], index) => (
            <g className={`landing-input-card landing-input-card-${index + 1}`} key={label} transform={`translate(74 ${y})`}>
              <rect width="158" height="52" rx="12" />
              <circle cx="26" cy="26" r="8" />
              <text x="48" y="32">{label}</text>
            </g>
          ))}
        </g>

        <path className="landing-animated-line landing-line-main" d="M236 184 C294 184 298 214 354 214 H430" />
        <path className="landing-animated-line landing-line-rag" d="M236 260 C310 260 314 318 432 318" />
        <path className="landing-animated-line landing-line-tool" d="M236 336 C294 336 310 416 432 416" />
        <path className="landing-animated-line landing-line-policy" d="M592 314 C640 314 648 304 692 304" />
        <path className="landing-animated-line landing-line-verdict" d="M770 304 C804 304 814 304 848 304" />

        <g className="landing-packet landing-packet-a"><circle r="7" /></g>
        <g className="landing-packet landing-packet-b"><circle r="7" /></g>
        <g className="landing-packet landing-packet-c"><circle r="7" /></g>

        <g className="landing-evidence-node" transform="translate(410 184)">
          <rect width="178" height="258" rx="20" />
          <text x="89" y="42">Evidence Layer</text>
          <g className="landing-evidence-chip" data-testid="privacy-signal" transform="translate(24 72)">
            <rect width="130" height="30" rx="15" />
            <circle cx="18" cy="15" r="5" />
            <text x="34" y="20">Privacy leakage</text>
          </g>
          <g className="landing-evidence-chip" data-testid="prompt-injection-signal" transform="translate(24 112)">
            <rect width="130" height="30" rx="15" />
            <circle cx="18" cy="15" r="5" />
            <text x="34" y="20">Prompt injection</text>
          </g>
          <g className="landing-evidence-chip" data-testid="rag-poisoning-signal" transform="translate(24 152)">
            <rect width="130" height="30" rx="15" />
            <circle cx="18" cy="15" r="5" />
            <text x="34" y="20">RAG poisoning</text>
          </g>
          <g className="landing-evidence-chip" data-testid="tool-misuse-signal" transform="translate(24 192)">
            <rect width="130" height="30" rx="15" />
            <circle cx="18" cy="15" r="5" />
            <text x="34" y="20">Tool misuse</text>
          </g>
        </g>

        <g className="landing-domain-node" transform="translate(610 110)">
          <rect width="198" height="90" rx="18" />
          <text x="99" y="38">Domain Signals</text>
          <text x="99" y="64">policy + sensitivity</text>
        </g>

        <g className="landing-policy-node" data-testid="policy-engine-node" transform="translate(662 236)" filter="url(#landingGlow)">
          <path d="M78 0 L144 24 V82 C144 128 112 158 78 176 C44 158 12 128 12 82 V24 Z" />
          <text x="78" y="70">Policy</text>
          <text x="78" y="96">Decision</text>
          <text x="78" y="122">Engine</text>
        </g>

        <g className="landing-verdict-node" data-testid="verdict-output-node" transform="translate(794 432)">
          <rect width="86" height="34" rx="17" className="landing-verdict landing-verdict-pass" />
          <text x="43" y="23">PASS</text>
          <rect width="86" height="34" x="-104" rx="17" className="landing-verdict landing-verdict-warn" />
          <text x="-61" y="23">WARN</text>
          <rect width="86" height="34" x="-208" rx="17" className="landing-verdict landing-verdict-fail" />
          <text x="-165" y="23">FAIL</text>
        </g>

        <g className="landing-threat-node landing-threat-node-1"><circle cx="272" cy="120" r="9" /><text x="292" y="126">Unsafe content</text></g>
        <g className="landing-threat-node landing-threat-node-2"><circle cx="294" cy="472" r="9" /><text x="314" y="478">Policy bypass</text></g>
        <g className="landing-threat-node landing-threat-node-3"><circle cx="612" cy="500" r="9" /><text x="632" y="506">Authorization risk</text></g>
      </svg>
    </div>
  )
}

function ThreatMicroAnimation({ tone }: { tone?: LandingCard['tone'] }) {
  return (
    <div className={`landing-threat-visual landing-threat-visual-${tone ?? 'evidence'}`} aria-hidden="true">
      <span className="landing-threat-bar landing-threat-bar-a" />
      <span className="landing-threat-bar landing-threat-bar-b" />
      <span className="landing-threat-bar landing-threat-bar-c" />
      <span className="landing-threat-shield" />
      <span className="landing-threat-node" />
    </div>
  )
}

function ArchitectureDiagram() {
  return (
    <div className="landing-architecture-diagram" aria-label="SpriCO external engine and final verdict architecture">
      <div className="landing-arch-column">
        <h3>Attack Engines</h3>
        <span>PyRIT</span>
        <span>garak</span>
        <span>future adapters</span>
      </div>
      <div className="landing-arch-column">
        <h3>Evidence Engines</h3>
        <span>scanner results</span>
        <span>transcripts</span>
        <span>RAG chunks</span>
        <span>tool calls</span>
        <span>judge outputs</span>
      </div>
      <div className="landing-arch-core">
        <h3>SpriCO Core</h3>
        <span>domain signals</span>
        <span>policy context</span>
        <span>authorization context</span>
        <strong>PolicyDecisionEngine</strong>
      </div>
      <div className="landing-arch-column">
        <h3>Outputs</h3>
        <span>findings</span>
        <span>evidence center</span>
        <span>dashboards</span>
        <span>reports</span>
      </div>
    </div>
  )
}

export default function LandingPage({ onNavigate }: LandingPageProps) {
  const navigate = (view: ViewName) => () => onNavigate(view)

  return (
    <div className="landing-page">
      <section className="landing-hero">
        <div className="landing-hero-copy">
          <p className="landing-kicker">SpriCO AI audit platform</p>
          <h1>Secure, audit, and red-team AI systems with evidence-backed verdicts.</h1>
          <p className="landing-subheadline">
            SpriCO combines attack engines, scanner evidence, domain policy packs, and human review to produce authorization-aware AI audit decisions.
          </p>
          <div className="landing-cta-row">
            <Button appearance="primary" size="large" onClick={navigate('chat')}>Start Interactive Audit</Button>
            <Button appearance="secondary" size="large" onClick={navigate('garak-scanner')}>Run LLM Vulnerability Scanner</Button>
            <Button appearance="secondary" size="large" onClick={navigate('red')}>Launch Red Team Campaign</Button>
          </div>
          <Button appearance="subtle" className="landing-secondary-link" onClick={navigate('evidence')}>
            Review Evidence Center
          </Button>
        </div>
        <HeroAnimation />
      </section>

      <section className="landing-trust-strip" aria-label="SpriCO platform claims">
        {trustClaims.map(claim => <span key={claim}>{claim}</span>)}
      </section>

      <section className="landing-section" aria-labelledby="workflow-heading">
        <div className="landing-section-heading">
          <p className="landing-kicker">How SpriCO works</p>
          <h2 id="workflow-heading">From target selection to evidence-backed review.</h2>
        </div>
        <div className="landing-workflow-grid">
          {workflowSteps.map((step, index) => (
            <article className="landing-workflow-step" key={step.title}>
              <span className="landing-step-number">{index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
              {step.view && step.button && (
                <Button appearance="subtle" onClick={navigate(step.view)}>{step.button}</Button>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section" aria-labelledby="threats-heading">
        <div className="landing-section-heading">
          <p className="landing-kicker">Threat categories</p>
          <h2 id="threats-heading">Signals stay explainable before policy decides.</h2>
        </div>
        <div className="landing-card-grid landing-threat-grid">
          {threatCards.map(card => (
            <article className="landing-card landing-threat-card" key={card.title}>
              <ThreatMicroAnimation tone={card.tone} />
              <h3>{card.title}</h3>
              <p>{card.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section landing-domain-section" aria-labelledby="domain-heading">
        <div className="landing-section-heading">
          <p className="landing-kicker">Domain packs</p>
          <h2 id="domain-heading">Domain-aware scoring for high-risk AI workflows</h2>
          <p>
            Generic scanners can find signals. SpriCO interprets them through industry policy, authorization context, data sensitivity, and evidence.
          </p>
        </div>
        <div className="landing-card-grid landing-domain-grid">
          {domainCards.map(card => (
            <article className="landing-card landing-domain-card" key={card.title}>
              <h3>{card.title}</h3>
              <p>{card.text}</p>
            </article>
          ))}
        </div>

        <div className="landing-healthcare-example" aria-labelledby="healthcare-example-heading">
          <div className="landing-section-heading">
            <p className="landing-kicker">Healthcare example</p>
            <h3 id="healthcare-example-heading">Healthcare example: patient-linked data risk</h3>
          </div>
          <div className="landing-card-grid landing-card-grid-four">
            {healthcareExamples.map(card => (
              <article className="landing-card landing-example-card" key={card.title}>
                <h4>{card.title}</h4>
                <p>{card.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-section landing-architecture-section" aria-labelledby="architecture-heading">
        <div className="landing-section-heading">
          <p className="landing-kicker">Architecture</p>
          <h2 id="architecture-heading">External engines feed evidence. SpriCO owns the verdict.</h2>
          <p>External engines provide attack/evidence signals. SpriCO produces the final policy-aware verdict.</p>
        </div>
        <ArchitectureDiagram />
      </section>

      <section className="landing-section" aria-labelledby="modules-heading">
        <div className="landing-section-heading">
          <p className="landing-kicker">Product modules</p>
          <h2 id="modules-heading">Open the workflow you need next.</h2>
        </div>
        <div className="landing-card-grid landing-module-grid">
          {moduleCards.map(card => (
            <article className="landing-card landing-module-card" key={card.title}>
              <div className="landing-card-icon">{card.icon}</div>
              <h3>{card.title}</h3>
              <p>{card.text}</p>
              {card.view && card.button && (
                <Button appearance="secondary" onClick={navigate(card.view)}>{card.button}</Button>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section landing-differentiation" aria-labelledby="differentiation-heading">
        <div>
          <p className="landing-kicker">Final verdict authority</p>
          <h2 id="differentiation-heading">Policy-aware decisions need more than scanner output.</h2>
          <p className="landing-authority-note">Final Verdict Authority: SpriCO PolicyDecisionEngine</p>
        </div>
        <ul>
          <li>Scanner output is evidence, not the final judge.</li>
          <li>Domain packs evaluate industry-specific risk.</li>
          <li>Authorization context decides whether sensitive disclosure is allowed or a violation.</li>
        </ul>
      </section>

      <section className="landing-footer-cta" aria-labelledby="footer-cta-heading">
        <h2 id="footer-cta-heading">Ready to test your AI system like an auditor?</h2>
        <div className="landing-cta-row">
          <Button appearance="primary" size="large" onClick={navigate('chat')}>Open Audit Workbench</Button>
          <Button appearance="secondary" size="large" onClick={navigate('policy')}>Configure Policies</Button>
          <Button appearance="secondary" size="large" onClick={navigate('evidence')}>View Evidence Center</Button>
        </div>
      </section>
    </div>
  )
}
