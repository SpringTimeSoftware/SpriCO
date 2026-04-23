import {
  Table,
  TableHeader,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  Badge,
  Button,
  Text,
} from '@fluentui/react-components'
import { CheckmarkRegular } from '@fluentui/react-icons'
import type { TargetInstance } from '../../types'
import { useTargetTableStyles } from './TargetTable.styles'

interface TargetTableProps {
  targets: TargetInstance[]
  activeTarget: TargetInstance | null
  onSetActiveTarget: (target: TargetInstance) => void
  onViewTarget: (target: TargetInstance) => void
  onArchiveTarget: (target: TargetInstance) => void
}

/** Format target_specific_params into a short human-readable string. */
function formatParams(params?: Record<string, unknown> | null): string {
  if (!params) return ''
  const parts: string[] = []
  for (const [key, val] of Object.entries(params)) {
    if (val == null) continue
    if (key === 'extra_body_parameters' && typeof val === 'object') {
      // Flatten nested extra body params for readability
      for (const [k, v] of Object.entries(val as Record<string, unknown>)) {
        parts.push(`${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
      }
    } else {
      parts.push(`${key}: ${typeof val === 'object' ? JSON.stringify(val) : String(val)}`)
    }
  }
  return parts.join(', ')
}

export default function TargetTable({ targets, activeTarget, onSetActiveTarget, onViewTarget, onArchiveTarget }: TargetTableProps) {
  const styles = useTargetTableStyles()

  const isActive = (target: TargetInstance): boolean =>
    activeTarget?.target_registry_name === target.target_registry_name

  return (
    <div className={styles.tableContainer}>
      <Table aria-label="Target instances" className={styles.table}>
        <colgroup>
          <col style={{ width: '240px' }} />
          <col style={{ width: '260px' }} />
          <col style={{ width: '180px' }} />
          <col style={{ width: '140px' }} />
          <col style={{ width: '280px' }} />
          <col style={{ width: '420px' }} />
        </colgroup>
        <TableHeader>
          <TableRow>
            <TableHeaderCell />
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Type</TableHeaderCell>
            <TableHeaderCell>Model</TableHeaderCell>
            <TableHeaderCell>Endpoint</TableHeaderCell>
            <TableHeaderCell>Parameters</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {targets.map((target) => (
            <TableRow
              key={target.target_registry_name}
              className={isActive(target) ? styles.activeRow : undefined}
            >
              <TableCell className={styles.actionCell}>
                <div className={styles.actionGroup}>
                  {isActive(target) ? (
                    <Badge appearance="filled" color="brand" icon={<CheckmarkRegular />}>
                      Active
                    </Badge>
                  ) : (
                    <Button
                      className={styles.actionButton}
                      appearance="primary"
                      size="small"
                      onClick={() => onSetActiveTarget(target)}
                    >
                      Set Active
                    </Button>
                  )}
                  <Button
                    className={styles.actionButton}
                    appearance="secondary"
                    size="small"
                    onClick={() => onViewTarget(target)}
                  >
                    View
                  </Button>
                  <Button
                    className={styles.actionButton}
                    appearance="subtle"
                    size="small"
                    onClick={() => onArchiveTarget(target)}
                  >
                    Archive
                  </Button>
                </div>
              </TableCell>
              <TableCell>
                <Text size={200} weight="semibold">
                  {target.display_name || target.target_registry_name}
                </Text>
              </TableCell>
              <TableCell>
                <Badge appearance="outline">{target.target_type}</Badge>
              </TableCell>
              <TableCell>
                <Text size={200}>{target.model_name || '—'}</Text>
              </TableCell>
              <TableCell>
                <Text size={200} className={styles.endpointCell} title={target.endpoint || undefined}>
                  {target.endpoint || '—'}
                </Text>
              </TableCell>
              <TableCell>
                <Text size={200} className={styles.paramsCell} title={formatParams(target.target_specific_params) || undefined}>
                  {formatParams(target.target_specific_params) || '—'}
                </Text>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
