import { makeStyles, tokens } from '@fluentui/react-components'

export const useChatWindowStyles = makeStyles({
  root: {
    display: 'flex',
    height: '100%',
    width: '100%',
    overflow: 'hidden',
  },
  chatArea: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    minWidth: 0,
    backgroundColor: tokens.colorNeutralBackground2,
    overflow: 'hidden',
  },
  ribbon: {
    height: '48px',
    minHeight: '48px',
    flexShrink: 0,
    backgroundColor: tokens.colorNeutralBackground3,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: `0 ${tokens.spacingHorizontalL}`,
    gap: tokens.spacingHorizontalM,
  },
  conversationInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    color: tokens.colorNeutralForeground2,
    fontSize: tokens.fontSizeBase300,
  },
  targetInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
  },
  noTarget: {
    color: tokens.colorNeutralForeground3,
    fontStyle: 'italic',
  },
  ribbonActions: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
  },
  interactiveSummaryBar: {
    flexShrink: 0,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground1,
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalL}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.spacingHorizontalL,
    flexWrap: 'wrap',
  },
  interactiveSummaryMeta: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXXS,
    minWidth: '260px',
  },
  interactiveSummaryTitle: {
    color: tokens.colorNeutralForeground1,
  },
  interactiveSummarySubtext: {
    color: tokens.colorNeutralForeground3,
  },
  interactiveSummaryBadges: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
    flexWrap: 'wrap',
  },
  savedReplayBanner: {
    flexShrink: 0,
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalL}`,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground2,
  },
})
