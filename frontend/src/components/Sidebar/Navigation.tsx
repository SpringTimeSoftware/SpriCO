import {
  Button,
  Menu,
  MenuDivider,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
} from '@fluentui/react-components'
import {
  ChatRegular,
  SettingsRegular,
  WeatherMoonRegular,
  WeatherSunnyRegular,
  ShieldRegular,
  DataTrendingRegular,
  ClipboardTaskRegular,
  DocumentDataRegular,
  TargetRegular,
} from '@fluentui/react-icons'
import { useNavigationStyles } from './Navigation.styles'

export type ViewName = 'chat' | 'history' | 'config' | 'audit' | 'dashboard'
  | 'heatmap-dashboard' | 'stability-dashboard' | 'findings' | 'prompt-variants' | 'target-help' | 'benchmark-library'
  | 'garak-scanner' | 'scanner-reports' | 'shield' | 'policy' | 'red' | 'evidence' | 'conditions' | 'open-source-components' | 'external-engines' | 'judge-models' | 'landing'

interface NavigationProps {
  currentView: ViewName
  onNavigate: (view: ViewName) => void
  onToggleTheme: () => void
  isDarkMode: boolean
}

type NavigationItem = {
  label: string
  view?: ViewName
  disabled?: boolean
  dividerBefore?: boolean
}

type NavigationGroup = {
  label: string
  view?: ViewName
  items: NavigationItem[]
}

export const NAVIGATION_GROUPS: NavigationGroup[] = [
  {
    label: 'Home',
    view: 'landing',
    items: [],
  },
  {
    label: 'Audit Workbench',
    items: [
      { label: 'Interactive Audit', view: 'chat' },
      { label: 'Attack History', view: 'history' },
      { label: 'Audit Runs', view: 'audit' },
      { label: 'Findings', view: 'findings' },
      { label: 'Evidence Center', view: 'evidence' },
    ],
  },
  {
    label: 'Scanners',
    items: [
      { label: 'LLM Vulnerability Scanner', view: 'garak-scanner' },
      { label: 'Scanner Run Reports', view: 'scanner-reports' },
      { label: 'Red Team Campaigns', view: 'red' },
      { label: 'Engine Diagnostics', disabled: true, dividerBefore: true },
      { label: 'garak Engine Diagnostics', view: 'garak-scanner' },
    ],
  },
  {
    label: 'Policies',
    items: [
      { label: 'Shield Check', view: 'shield' },
      { label: 'Policies', view: 'policy' },
      { label: 'Custom Conditions', view: 'conditions' },
      { label: 'Authorization Context - coming soon', disabled: true },
    ],
  },
  {
    label: 'Dashboards',
    items: [
      { label: 'Structured Dashboard', view: 'dashboard' },
      { label: 'Heatmap Dashboard', view: 'heatmap-dashboard' },
      { label: 'Stability Dashboard', view: 'stability-dashboard' },
    ],
  },
  {
    label: 'Library',
    items: [
      { label: 'Benchmark Library', view: 'benchmark-library' },
      { label: 'Prompt Variants', view: 'prompt-variants' },
      { label: 'Attack Templates - coming soon', disabled: true },
    ],
  },
  {
    label: 'Settings',
    items: [
      { label: 'Configuration', view: 'config' },
      { label: 'Target Help', view: 'target-help' },
      { label: 'Legal', disabled: true, dividerBefore: true },
      { label: 'Open Source Components', view: 'open-source-components' },
      { label: 'External Engine Metadata', view: 'external-engines' },
      { label: 'Judge Models', view: 'judge-models' },
    ],
  },
]

const QUICK_ACCESS: Array<{ label: string; view: ViewName; icon: JSX.Element }> = [
  { label: 'Interactive Audit', view: 'chat', icon: <ChatRegular /> },
  { label: 'Audit Runs', view: 'audit', icon: <ClipboardTaskRegular /> },
  { label: 'Red Team Campaigns', view: 'red', icon: <TargetRegular /> },
  { label: 'Evidence Center', view: 'evidence', icon: <DocumentDataRegular /> },
  { label: 'Policies', view: 'policy', icon: <ShieldRegular /> },
  { label: 'Structured Dashboard', view: 'dashboard', icon: <DataTrendingRegular /> },
  { label: 'Configuration', view: 'config', icon: <SettingsRegular /> },
]

function groupIsActive(group: NavigationGroup, currentView: ViewName): boolean {
  return group.view === currentView || group.items.some(item => item.view === currentView)
}

export function GroupedNavigation({ currentView, onNavigate }: Pick<NavigationProps, 'currentView' | 'onNavigate'>) {
  const styles = useNavigationStyles()

  return (
    <nav className={styles.groupNav} aria-label="Primary navigation">
      {NAVIGATION_GROUPS.map(group => group.view ? (
        <Button
          key={group.label}
          className={styles.groupButton}
          data-active={groupIsActive(group, currentView)}
          appearance="subtle"
          onClick={() => onNavigate(group.view as ViewName)}
        >
          {group.label}
        </Button>
      ) : (
        <Menu key={group.label} positioning="below-start">
          <MenuTrigger disableButtonEnhancement>
            <Button
              className={styles.groupButton}
              data-active={groupIsActive(group, currentView)}
              appearance="subtle"
            >
              {group.label}
            </Button>
          </MenuTrigger>
          <MenuPopover>
            <MenuList>
              {group.items.map(item => (
                <div key={item.label}>
                  {item.dividerBefore && <MenuDivider />}
                  <MenuItem
                    disabled={item.disabled}
                    onClick={() => {
                      if (item.view) {
                        onNavigate(item.view)
                      }
                    }}
                  >
                    {item.label}
                  </MenuItem>
                </div>
              ))}
            </MenuList>
          </MenuPopover>
        </Menu>
      ))}
    </nav>
  )
}

export default function Navigation({ currentView, onNavigate, onToggleTheme, isDarkMode }: NavigationProps) {
  const styles = useNavigationStyles()

  return (
    <div className={styles.root}>
      {QUICK_ACCESS.map(item => (
        <Button
          key={item.view}
          className={styles.navButton}
          data-active={currentView === item.view}
          appearance="subtle"
          icon={item.icon}
          title={item.label}
          aria-label={item.label}
          onClick={() => onNavigate(item.view)}
        />
      ))}

      <div className={styles.spacer} />

      <Button
        className={styles.navButton}
        appearance="subtle"
        icon={isDarkMode ? <WeatherSunnyRegular /> : <WeatherMoonRegular />}
        onClick={onToggleTheme}
        title={isDarkMode ? 'Light Mode' : 'Dark Mode'}
        aria-label={isDarkMode ? 'Light Mode' : 'Dark Mode'}
      />
    </div>
  )
}
