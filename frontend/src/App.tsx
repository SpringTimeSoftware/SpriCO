import { useState, useCallback, useEffect } from 'react'
import { FluentProvider, webLightTheme, webDarkTheme } from '@fluentui/react-components'
import MainLayout from './components/Layout/MainLayout'
import ChatWindow from './components/Chat/ChatWindow'
import TargetConfig from './components/Config/TargetConfig'
import AttackHistory from './components/History/AttackHistory'
import ActivityHistoryPage from './components/History/ActivityHistoryPage'
import { DEFAULT_HISTORY_FILTERS } from './components/History/historyFilters'
import type { HistoryFilters } from './components/History/historyFilters'
import type { ViewName } from './components/Sidebar/Navigation'
import { ConnectionBanner } from './components/ConnectionBanner'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ConnectionHealthProvider, useConnectionHealth } from './hooks/useConnectionHealth'
import AuditPage from './components/Audit/AuditPage'
import DashboardPage from './components/Audit/DashboardPage'
import HeatmapDashboardPage from './components/Audit/HeatmapDashboardPage'
import PromptVariantsPage from './components/Audit/PromptVariantsPage'
import StabilityDashboardPage from './components/Audit/StabilityDashboardPage'
import TargetHelpPage from './components/Audit/TargetHelpPage'
import BenchmarkLibraryPage from './components/Audit/BenchmarkLibraryPage'
import GarakScannerPage from './components/SpriCO/GarakScannerPage'
import ScannerRunReportsPage from './components/SpriCO/ScannerRunReportsPage'
import ShieldPage from './components/SpriCO/ShieldPage'
import PolicyPage from './components/SpriCO/PolicyPage'
import RedPage from './components/SpriCO/RedPage'
import EvidencePage from './components/SpriCO/EvidencePage'
import CustomConditionsPage from './components/SpriCO/CustomConditionsPage'
import OpenSourceComponentsPage from './components/SpriCO/OpenSourceComponentsPage'
import ExternalEngineMetadataPage from './components/SpriCO/ExternalEngineMetadataPage'
import JudgeModelsPage from './components/SpriCO/JudgeModelsPage'
import DiagnosticsPage from './components/SpriCO/DiagnosticsPage'
import LandingPage from './components/Landing/LandingPage'
import { versionApi, attacksApi, targetsApi } from './services/api'
import type { TargetInstance, TargetInfo } from './types'

const AUTO_DISMISS_MS = 5_000
const DEFAULT_GLOBAL_LABELS: Record<string, string> = {}
const BRAND_NAME = 'SpriCO AI Audit Platform'
const THEME_STORAGE_KEY = 'siddhi-audit-theme'

export interface AuditFindingsFilters {
  verdict?: 'ALL' | 'FAIL' | 'WARN' | 'PASS'
  category?: string
  severity?: string
  search?: string
}

type AuditOriginView = 'chat' | 'dashboard' | 'heatmap-dashboard' | 'stability-dashboard' | 'benchmark-library' | 'audit' | null

function ConnectionBannerContainer() {
  const { status, reconnectCount } = useConnectionHealth()
  const [showReconnected, setShowReconnected] = useState(false)

  useEffect(() => {
    if (reconnectCount > 0) {
      setShowReconnected(true)
      const timer = setTimeout(() => setShowReconnected(false), AUTO_DISMISS_MS)
      return () => clearTimeout(timer)
    }
  }, [reconnectCount])

  if (status === 'connected' && !showReconnected) {
    return null
  }

  return <ConnectionBanner status={status} />
}

function App() {
  const [isDarkMode, setIsDarkMode] = useState(() => {
    if (typeof window === 'undefined') {
      return true
    }
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    return stored ? stored === 'dark' : true
  })
  const [currentView, setCurrentView] = useState<ViewName>('landing')
  const [selectedAuditRunId, setSelectedAuditRunId] = useState<string | null>(null)
  const [selectedAuditFilters, setSelectedAuditFilters] = useState<AuditFindingsFilters | null>(null)
  const [selectedAuditOrigin, setSelectedAuditOrigin] = useState<AuditOriginView>(null)
  const [activeTarget, setActiveTarget] = useState<TargetInstance | null>(null)
  const [globalLabels, setGlobalLabels] = useState<Record<string, string>>({ ...DEFAULT_GLOBAL_LABELS })
  /** True while loading a historical attack from the history view */
  const [isLoadingAttack, setIsLoadingAttack] = useState(false)
  /** Persisted filter state for the history view */
  const [historyFilters, setHistoryFilters] = useState<HistoryFilters>({ ...DEFAULT_HISTORY_FILTERS })

  // Fetch default labels from backend configuration on startup
  useEffect(() => {
    versionApi.getVersion()
      .then((data) => {
        if (data.default_labels && Object.keys(data.default_labels).length > 0) {
          setGlobalLabels(prev => ({ ...prev, ...data.default_labels }))
        }
      })
      .catch(() => { /* version fetch handled elsewhere */ })
  }, [])

  useEffect(() => {
    targetsApi.getActiveTarget()
      .then((target) => {
        setActiveTarget(target)
      })
      .catch(() => { /* no persisted active target */ })
  }, [])

  useEffect(() => {
    const themeName = isDarkMode ? 'dark' : 'light'
    document.title = BRAND_NAME
    document.documentElement.setAttribute('data-theme', themeName)
    window.localStorage.setItem(THEME_STORAGE_KEY, themeName)
  }, [isDarkMode])

  const handleSetActiveTarget = useCallback((target: TargetInstance | null) => {
    if (target === null) {
      setActiveTarget(null)
      return
    }
    setActiveTarget(prev => {
      const isSame = prev &&
        prev.target_registry_name === target.target_registry_name &&
        prev.target_type === target.target_type &&
        (prev.endpoint ?? '') === (target.endpoint ?? '') &&
        (prev.model_name ?? '') === (target.model_name ?? '')
      if (isSame) return prev
      // Switching targets no longer clears the loaded attack.  The cross-target
      // guard in ChatWindow prevents sending to a mismatched target, and the
      // backend enforces this server-side as well.  Clearing state here was
      // confusing because navigating to config to pick the *correct* target
      // would wipe the conversation the user was trying to continue.
      return target
    })
  }, [])
  /** The AttackResult's primary key (set on first message). */
  const [attackResultId, setAttackResultId] = useState<string | null>(null)
  /** The attack's primary conversation_id (set on first message). */
  const [conversationId, setConversationId] = useState<string | null>(null)
  /** The currently active conversation (may be main or a related conversation). */
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  /** Labels that the currently loaded attack was created with (for operator locking). */
  const [attackLabels, setAttackLabels] = useState<Record<string, string> | null>(null)
  /** Target info from the currently loaded historical attack (for cross-target guard). */
  const [attackTarget, setAttackTarget] = useState<TargetInfo | null>(null)
  /** Number of related conversations for the currently loaded attack. */
  const [relatedConversationCount, setRelatedConversationCount] = useState(0)
  /** Saved Interactive Audit run loaded from audit.db when PyRIT memory has no attack session. */
  const [savedInteractiveRunId, setSavedInteractiveRunId] = useState<string | null>(null)

  const clearAttackState = useCallback(() => {
    setAttackResultId(null)
    setConversationId(null)
    setActiveConversationId(null)
    setAttackLabels(null)
    setAttackTarget(null)
    setRelatedConversationCount(0)
    setSavedInteractiveRunId(null)
  }, [])

  const handleNewAttack = () => {
    clearAttackState()
  }

  const handleConversationCreated = useCallback((arId: string, convId: string) => {
    setAttackResultId(arId)
    setConversationId(convId)
    setActiveConversationId(convId)
    // New attack was created by the current user — use their global labels
    setAttackLabels(null)
    // Record the target used for this attack so the cross-target guard
    // fires if the user switches targets mid-conversation.
    if (activeTarget) {
      const { target_type, endpoint, model_name } = activeTarget
      setAttackTarget({ target_type, endpoint, model_name })
    }
  }, [activeTarget])

  const handleSelectConversation = useCallback((convId: string) => {
    setActiveConversationId(convId)
    // Messages will be loaded by ChatWindow's useEffect
  }, [])

  const handleOpenAttack = useCallback(async (openAttackResultId: string) => {
    setSavedInteractiveRunId(null)
    setAttackResultId(openAttackResultId)
    setIsLoadingAttack(true)
    setCurrentView('chat')
    // Fetch attack info to get conversation_id and stored labels (for operator locking)
    try {
      const attack = await attacksApi.getAttack(openAttackResultId)
      setConversationId(attack.conversation_id)
      setActiveConversationId(attack.conversation_id)
      setAttackLabels(attack.labels ?? {})
      setAttackTarget(attack.target ?? null)
      setRelatedConversationCount(attack.related_conversation_ids?.length ?? 0)
    } catch {
      clearAttackState()
    } finally {
      setIsLoadingAttack(false)
    }
  }, [clearAttackState])

  const handleOpenSavedInteractiveAudit = useCallback((runId: string) => {
    clearAttackState()
    setSavedInteractiveRunId(runId)
    setCurrentView('chat')
  }, [clearAttackState])

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode)
  }

  const handleNavigate = useCallback((view: ViewName) => {
    setCurrentView(view)
    if (view !== 'findings') {
      setSelectedAuditOrigin(null)
      return
    }
    if (!selectedAuditRunId) {
      setSelectedAuditOrigin(null)
    }
  }, [selectedAuditRunId])

  return (
    <ErrorBoundary>
      <ConnectionHealthProvider>
        <FluentProvider theme={isDarkMode ? webDarkTheme : webLightTheme}>
          <ConnectionBannerContainer />
          <MainLayout
            currentView={currentView}
            onNavigate={handleNavigate}
            onToggleTheme={toggleTheme}
            isDarkMode={isDarkMode}
            brandingName={BRAND_NAME}
          >
            {currentView === 'landing' && (
              <LandingPage onNavigate={handleNavigate} />
            )}
            {currentView === 'chat' && (
              <ChatWindow
                onNewAttack={handleNewAttack}
                onOpenStructuredRun={(runId) => {
                  setSelectedAuditRunId(runId)
                  setSelectedAuditFilters(null)
                  setSelectedAuditOrigin('chat')
                  setCurrentView('findings')
                }}
                activeTarget={activeTarget}
                savedInteractiveRunId={savedInteractiveRunId}
                attackResultId={attackResultId}
                conversationId={conversationId}
                activeConversationId={activeConversationId}
                onConversationCreated={handleConversationCreated}
                onSelectConversation={handleSelectConversation}
                labels={globalLabels}
                onLabelsChange={setGlobalLabels}
                onNavigate={setCurrentView}
                attackLabels={attackLabels}
                attackTarget={attackTarget}
                isLoadingAttack={isLoadingAttack}
                relatedConversationCount={relatedConversationCount}
              />
            )}
            {currentView === 'config' && (
              <TargetConfig
                activeTarget={activeTarget}
                onSetActiveTarget={handleSetActiveTarget}
                onOpenTargetHelp={() => setCurrentView('target-help')}
              />
            )}
            {currentView === 'history' && (
              <AttackHistory
                onOpenAttack={handleOpenAttack}
                onOpenSavedInteractiveAudit={handleOpenSavedInteractiveAudit}
                onOpenAuditRuns={() => setCurrentView('audit')}
                onNavigate={setCurrentView}
                filters={historyFilters}
                onFiltersChange={setHistoryFilters}
              />
            )}
            {currentView === 'activity-history' && (
              <ActivityHistoryPage onNavigate={setCurrentView} />
            )}
            {currentView === 'audit' && (
              <AuditPage
                initialRunId={selectedAuditRunId}
                initialFilters={selectedAuditFilters}
                onRunOpened={() => {
                  setSelectedAuditRunId(null)
                  setSelectedAuditFilters(null)
                }}
              />
            )}
            {currentView === 'findings' && (
              <AuditPage
                initialRunId={selectedAuditRunId}
                initialFilters={selectedAuditFilters}
                forcedWorkspaceView="findings"
                backLink={selectedAuditOrigin ? {
                  label: selectedAuditOrigin === 'chat'
                    ? 'Back To Interactive Audit'
                    : selectedAuditOrigin === 'dashboard'
                    ? 'Back To Structured Dashboard'
                    : selectedAuditOrigin === 'heatmap-dashboard'
                      ? 'Back To Heatmap Dashboard'
                      : selectedAuditOrigin === 'stability-dashboard'
                        ? 'Back To Stability Dashboard'
                        : selectedAuditOrigin === 'benchmark-library'
                          ? 'Back To Benchmark Library'
                          : 'Back To Audit Workstation',
                  onClick: () => setCurrentView(selectedAuditOrigin),
                } : undefined}
                onRunOpened={() => {
                  setSelectedAuditRunId(null)
                  setSelectedAuditFilters(null)
                }}
              />
            )}
            {currentView === 'dashboard' && (
              <DashboardPage
                onOpenRun={(runId, filters) => {
                  setSelectedAuditRunId(runId)
                  setSelectedAuditFilters(filters ?? null)
                  setSelectedAuditOrigin('dashboard')
                  setCurrentView('findings')
                }}
              />
            )}
            {currentView === 'heatmap-dashboard' && (
              <HeatmapDashboardPage
                onOpenRun={(runId, filters) => {
                  setSelectedAuditRunId(runId)
                  setSelectedAuditFilters(filters ?? null)
                  setSelectedAuditOrigin('heatmap-dashboard')
                  setCurrentView('findings')
                }}
                onOpenPromptVariants={() => setCurrentView('prompt-variants')}
                onOpenFindings={() => {
                  setSelectedAuditOrigin('heatmap-dashboard')
                  setCurrentView('findings')
                }}
              />
            )}
            {currentView === 'prompt-variants' && (
              <PromptVariantsPage
                onOpenRun={(runId) => {
                  setSelectedAuditRunId(runId)
                  setSelectedAuditFilters(null)
                  setSelectedAuditOrigin('audit')
                  setCurrentView('findings')
                }}
              />
            )}
            {currentView === 'stability-dashboard' && (
              <StabilityDashboardPage
                onOpenRun={(runId) => {
                  setSelectedAuditRunId(runId)
                  setSelectedAuditFilters(null)
                  setSelectedAuditOrigin('stability-dashboard')
                  setCurrentView('findings')
                }}
              />
            )}
            {currentView === 'benchmark-library' && (
              <BenchmarkLibraryPage
                onOpenRun={(runId) => {
                  setSelectedAuditRunId(runId)
                  setSelectedAuditFilters(null)
                  setSelectedAuditOrigin('benchmark-library')
                  setCurrentView('findings')
                }}
              />
            )}
            {currentView === 'target-help' && (
              <TargetHelpPage />
            )}
            {currentView === 'garak-scanner' && (
              <GarakScannerPage onNavigate={setCurrentView} />
            )}
            {currentView === 'scanner-reports' && (
              <ScannerRunReportsPage onNavigate={setCurrentView} />
            )}
            {currentView === 'shield' && (
              <ShieldPage />
            )}
            {currentView === 'policy' && (
              <PolicyPage />
            )}
            {currentView === 'red' && (
              <RedPage />
            )}
            {currentView === 'evidence' && (
              <EvidencePage />
            )}
            {currentView === 'conditions' && (
              <CustomConditionsPage />
            )}
            {currentView === 'open-source-components' && (
              <OpenSourceComponentsPage />
            )}
            {currentView === 'external-engines' && (
              <ExternalEngineMetadataPage />
            )}
            {currentView === 'judge-models' && (
              <JudgeModelsPage />
            )}
            {currentView === 'diagnostics' && (
              <DiagnosticsPage />
            )}
          </MainLayout>
        </FluentProvider>
      </ConnectionHealthProvider>
    </ErrorBoundary>
  )
}

export default App
