import type { TargetCapability, TargetInstance } from '../../types'

export type AuditMode = 'COMPLIANCE' | 'ROBUSTNESS' | 'ADVANCED'
export type SeedStrategy = 'FIXED' | 'PER_RUN_RANDOM' | 'SEQUENTIAL'

export interface ParameterHelpDefinition {
  key: string
  label: string
  short_help: string
  long_help: string[]
  supported_targets?: string[]
  visibility_rules?: Array<'supports_top_k'>
}

export const PARAMETER_HELP: ParameterHelpDefinition[] = [
  {
    key: 'temperature',
    label: 'Temperature',
    short_help: 'Controls how predictable or varied the model’s next-token choices are. Lower = more repeatable. Higher = more varied.',
    long_help: [
      'Temperature controls how strongly the model favors its highest-probability next-token options.',
      'Lower values produce more repeatable, tightly constrained outputs. Higher values allow more variation and can surface brittle or inconsistent behavior.',
      'For Compliance Audit, keep it low for reproducible evidence. For Robustness Audit, moderate values help expose instability and worst-case outcomes.',
    ],
  },
  {
    key: 'run_count',
    label: 'Run Count',
    short_help: 'How many times the same test is executed. Higher run count helps measure consistency and worst-case behavior.',
    long_help: [
      'Run Count determines how many physical executions are performed for the same logical test case.',
      'Repeated execution helps measure stability score, pass or fail rate, and worst-case behavior that a single run may miss.',
      'Higher run counts increase execution time and cost, but provide stronger robustness evidence.',
    ],
  },
  {
    key: 'top_p',
    label: 'Top P',
    short_help: 'Limits the model to the smallest set of likely next-token candidates whose combined probability reaches P. Lower = narrower choices.',
    long_help: [
      'Top P uses nucleus sampling: the model keeps the smallest pool of next-token candidates whose combined probability reaches the chosen threshold.',
      'This is related to Temperature, but it works differently. Temperature reshapes probabilities. Top P trims the candidate pool.',
      'Most users should avoid tuning Temperature and Top P aggressively at the same time unless they are intentionally studying sampling effects.',
    ],
  },
  {
    key: 'top_k',
    label: 'Top K',
    short_help: 'Limits the model to the top K next-token candidates. Smaller K = tighter shortlist.',
    long_help: [
      'Top K restricts token selection to a fixed shortlist of the K most likely next tokens.',
      'Smaller K creates a tighter shortlist and more constrained outputs.',
      'Not every provider or target supports Top K. Show and use it only when the selected target can accept it.',
    ],
    visibility_rules: ['supports_top_k'],
  },
  {
    key: 'seed',
    label: 'Seed',
    short_help: 'A numeric value used to control sampling randomness. Same seed + same settings usually gives more repeatable output.',
    long_help: [
      'Seed is the numeric value used to initialize sampling randomness for a run.',
      'Keeping the same seed with the same model version, context, and settings usually improves repeatability.',
      'If the model version, system prompt, context, or retrieval state changes, the output can still change even with the same seed.',
    ],
  },
  {
    key: 'fixed_seed',
    label: 'Fixed Seed',
    short_help: 'Keeps the seed constant across runs for better repeatability and comparison.',
    long_help: [
      'Fixed Seed keeps the same seed value across runs so that variability is reduced and comparisons are more controlled.',
      'Use this when you need report-grade reproducibility or when comparing small prompt changes.',
      'Turn it off when you want robustness testing to explore different sampling paths.',
    ],
  },
  {
    key: 'seed_strategy',
    label: 'Seed Strategy',
    short_help: 'Controls how seeds are assigned across multiple runs.',
    long_help: [
      'Seed Strategy controls how seeds are assigned when a test runs multiple times.',
      'Per Run Random gives each run a different random seed and is best for robustness testing and instability discovery.',
      'Sequential uses a predictable sequence of seeds across runs and is good for repeatable robustness testing. Fixed keeps one seed for every run.',
    ],
  },
  {
    key: 'max_tokens',
    label: 'Max Tokens',
    short_help: 'Maximum response length the model is allowed to generate. Low values can shorten or cut off output.',
    long_help: [
      'Max Tokens limits how long the response is allowed to be.',
      'If this value is too low, the model may be truncated before it reveals a refusal, rationale, or harmful continuation.',
      'For audits, keep it high enough to avoid accidental truncation that could hide true behavior.',
    ],
  },
  {
    key: 'token',
    label: 'Token',
    short_help: 'A small text unit used by the model. A token may be a full word, part of a word, or punctuation.',
    long_help: [
      'Models generate text one token at a time.',
      'A token can be a whole word, part of a word, a number, or punctuation depending on the tokenizer.',
      'Generation controls act on the model’s token-by-token candidate selection process.',
    ],
  },
  {
    key: 'candidate_tokens',
    label: 'Candidate Tokens',
    short_help: 'The possible next-token options the model is considering at a given step.',
    long_help: [
      'Candidate tokens are the possible next-token options the model is considering at each generation step.',
      'Temperature reshapes the probability distribution over those candidates. Top P and Top K reduce the candidate pool before selection.',
      'The process then repeats token by token until the response stops or Max Tokens is reached.',
    ],
  },
]

export const MODE_RECOMMENDATIONS: Record<AuditMode, string[]> = {
  COMPLIANCE: [
    'Temperature: low',
    'Fixed Seed: on',
    'Run Count: 1',
    'Top P: default or fixed',
    'Max Tokens: enough to avoid accidental truncation',
  ],
  ROBUSTNESS: [
    'Temperature: moderate',
    'Fixed Seed: off',
    'Seed Strategy: Per Run Random or Sequential',
    'Run Count: 5+',
    'Max Tokens: high enough to observe full behavior',
  ],
  ADVANCED: [
    'Expose all supported parameters',
    'Change one parameter at a time when comparing results',
    'Document any non-default settings in the report',
  ],
}

export const SEED_STRATEGY_HELP: Record<SeedStrategy, string> = {
  FIXED: 'Keeps the same seed for every run. Best for controlled repetition and close prompt comparison.',
  PER_RUN_RANDOM: 'Each run gets a different random seed. Best for robustness testing and instability discovery.',
  SEQUENTIAL: 'Uses a predictable sequence of seeds across runs. Good for repeatable robustness testing.',
}

const TARGET_CODE_BY_TYPE: Record<string, string> = {
  OpenAIChatTarget: 'OPENAI_CHAT_TARGET',
  OpenAICompletionTarget: 'OPENAI_COMPLETION_TARGET',
  OpenAIResponseTarget: 'OPENAI_RESPONSE_TARGET',
  OpenAIImageTarget: 'OPENAI_IMAGE_TARGET',
  OpenAIVideoTarget: 'OPENAI_VIDEO_TARGET',
  OpenAITTSTarget: 'OPENAI_TTS_TARGET',
  HTTPTarget: 'HTTP_TARGET',
  BrowserTarget: 'BROWSER_TARGET',
  PlaywrightTarget: 'BROWSER_TARGET',
  CustomTarget: 'CUSTOM_TARGET',
}

export function targetSupportsTopK(target: TargetInstance | null, capabilities: TargetCapability[]): boolean {
  if (!target) return false
  const capabilityCode = TARGET_CODE_BY_TYPE[target.target_type]
  const capability = capabilityCode ? capabilities.find(item => item.target_code === capabilityCode) : undefined
  if (capability && ['chat', 'completion', 'response'].includes(capability.api_style) && capability.modality === 'text') {
    return true
  }
  return ['OpenAIChatTarget', 'OpenAICompletionTarget', 'OpenAIResponseTarget'].includes(target.target_type)
}

export function getVisibleParameterHelp(params: {
  supportsTopK: boolean
}): ParameterHelpDefinition[] {
  return PARAMETER_HELP.filter(entry => {
    if (!entry.visibility_rules?.length) return true
    return entry.visibility_rules.every(rule => {
      if (rule === 'supports_top_k') return params.supportsTopK
      return true
    })
  })
}
