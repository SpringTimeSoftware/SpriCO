import { makeStyles, tokens } from '@fluentui/react-components'

export const useTargetTableStyles = makeStyles({
  tableContainer: {
    flex: 1,
    overflow: 'auto',
    maxHeight: '800px',
    minWidth: 0,
  },
  table: {
    tableLayout: 'fixed',
    width: 'max-content',
    minWidth: '100%',
  },
  actionCell: {
    width: '240px',
    minWidth: '240px',
  },
  actionGroup: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '6px',
    maxWidth: '220px',
  },
  actionButton: {
    minWidth: '64px',
    whiteSpace: 'nowrap',
  },
  activeRow: {
    backgroundColor: tokens.colorBrandBackground2,
  },
  endpointCell: {
    display: 'block',
    maxWidth: '280px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  paramsCell: {
    display: 'block',
    maxWidth: '420px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
})
