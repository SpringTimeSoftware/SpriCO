import { useEffect, useState } from 'react'
import {
  Text,
  Tooltip,
} from '@fluentui/react-components'
import { versionApi } from '../../services/api'
import Navigation, { GroupedNavigation, type ViewName } from '../Sidebar/Navigation'
import { useMainLayoutStyles } from './MainLayout.styles'

interface MainLayoutProps {
  children: React.ReactNode
  currentView: ViewName
  onNavigate: (view: ViewName) => void
  onToggleTheme: () => void
  isDarkMode: boolean
  brandingName: string
}

export default function MainLayout({
  children,
  currentView,
  onNavigate,
  onToggleTheme,
  isDarkMode,
  brandingName,
}: MainLayoutProps) {
  const styles = useMainLayoutStyles()
  const [version, setVersion] = useState<string>('Loading...')
  const [databaseInfo, setDatabaseInfo] = useState<string | null>(null)
  const [devLoadedAt] = useState(() => new Date().toLocaleString())

  useEffect(() => {
    versionApi.getVersion()
      .then(data => {
        setVersion(data.display || data.version)
        setDatabaseInfo(data.database_info ?? null)
      })
      .catch(() => setVersion('Unknown'))
  }, [])

  const isLandingView = currentView === 'landing'

  return (
    <div className={styles.root}>
      <div className={styles.topBar}>
        <div className={styles.brandBlock}>
          <Tooltip
            content={<>
              {`${brandingName} ${version}`}
              {databaseInfo && <><br />{databaseInfo}</>}
              {import.meta.env.DEV && <><br />{`Dev build loaded ${devLoadedAt}`}</>}
            </>}
            relationship="description"
          >
            <button
              type="button"
              className={styles.brandButton}
              onClick={() => onNavigate('landing')}
              aria-label="Open Home"
            >
              <Text className={styles.title}>{brandingName}</Text>
            </button>
          </Tooltip>
        </div>
        <GroupedNavigation currentView={currentView} onNavigate={onNavigate} />
        <div className={styles.spacer} />
      </div>
      <div className={styles.contentArea}>
        {!isLandingView && (
          <aside className={styles.sidebar} aria-label="Quick access navigation">
            <Navigation
              currentView={currentView}
              onNavigate={onNavigate}
              onToggleTheme={onToggleTheme}
              isDarkMode={isDarkMode}
            />
          </aside>
        )}
        <main className={styles.main}>{children}</main>
      </div>
    </div>
  )
}
