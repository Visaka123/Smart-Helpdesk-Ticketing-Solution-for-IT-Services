import { Chip } from '@mui/material'

const statusConfig: Record<string, { label: string; color: 'success' | 'warning' | 'error' | 'default' | 'info' }> = {
  open: { label: 'Open', color: 'warning' },
  closed: { label: 'Closed', color: 'success' },
  resolved: { label: 'Resolved', color: 'success' },
  pending: { label: 'Pending', color: 'info' },
  'in-progress': { label: 'In Progress', color: 'info' },
}

const priorityConfig: Record<string, { label: string; color: 'error' | 'warning' | 'info' | 'default' }> = {
  high: { label: 'High', color: 'error' },
  medium: { label: 'Medium', color: 'warning' },
  low: { label: 'Low', color: 'info' },
}

export function StatusBadge({ status }: { status: string }) {
  const cfg = statusConfig[status?.toLowerCase()] || { label: status, color: 'default' as const }
  return <Chip label={cfg.label} color={cfg.color} size="small" variant="outlined" />
}

export function PriorityBadge({ priority }: { priority: string }) {
  const cfg = priorityConfig[priority?.toLowerCase()] || { label: priority, color: 'default' as const }
  return <Chip label={cfg.label} color={cfg.color} size="small" />
}
