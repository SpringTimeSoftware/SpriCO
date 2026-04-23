import { makeStyles, tokens } from '@fluentui/react-components'

export const useNavigationStyles = makeStyles({
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    padding: tokens.spacingVerticalM,
    alignItems: 'center',
    gap: tokens.spacingVerticalS,
  },
  navButton: {
    width: '44px',
    height: '44px',
    minWidth: '44px',
    padding: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: tokens.colorNeutralForeground2,
    borderRadius: tokens.borderRadiusMedium,
    transitionDuration: '160ms',
    transitionProperty: 'background-color, color, box-shadow, border-color, transform',
    '&:hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
      color: tokens.colorBrandForeground1,
      transform: 'translateY(-1px)',
    },
    '&[data-active="true"]': {
      backgroundColor: tokens.colorBrandBackground2,
      color: tokens.colorBrandForeground1,
      borderRadius: tokens.borderRadiusMedium,
      boxShadow: `inset 0 0 0 1px ${tokens.colorBrandStroke1}`,
    },
  },
  spacer: {
    flex: 1,
  },
  groupNav: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
    flexWrap: 'wrap',
    minWidth: 0,
  },
  groupButton: {
    minWidth: 'auto',
    borderRadius: tokens.borderRadiusMedium,
    color: tokens.colorNeutralForeground2,
    fontWeight: tokens.fontWeightSemibold,
    '&:hover': {
      color: tokens.colorBrandForeground1,
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
    '&[data-active="true"]': {
      color: tokens.colorBrandForeground1,
      backgroundColor: tokens.colorBrandBackground2,
      boxShadow: `inset 0 0 0 1px ${tokens.colorBrandStroke1}`,
    },
  },
})
