import React from 'react'
import { Box, Chip, Tooltip } from '@mui/material'
import CircleIcon from '@mui/icons-material/Circle'
import BeachAccessIcon from '@mui/icons-material/BeachAccess'
import NightlightIcon from '@mui/icons-material/Nightlight'
import BlockIcon from '@mui/icons-material/Block'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import type { AgentAvailability } from '../../types'

export type AvailStatus = 'available' | 'on_leave' | 'off_shift' | 'at_capacity' | 'over_capacity'

export function getAvailStatus(agent: AgentAvailability): AvailStatus {
  if ((agent as any).status) return (agent as any).status as AvailStatus
  if (agent.on_leave) return 'on_leave'
  if (!agent.on_shift && !agent.on_call) return 'off_shift'
  if (agent.open_tickets > agent.ticket_cap) return 'over_capacity'
  if (!agent.below_cap) return 'at_capacity'
  return 'available'
}

const STATUS_CONFIG: Record<AvailStatus, { label: string; color: string; bg: string; border: string; icon: React.ReactElement }> = {
  available:     { label: 'Available',     color: '#047857', bg: '#ECFDF5', border: '#A7F3D0', icon: <CheckCircleIcon style={{ fontSize: 12, color: '#047857' }} /> },
  on_leave:      { label: 'On leave',      color: '#B45309', bg: '#FEF3C7', border: '#FDE68A', icon: <BeachAccessIcon  style={{ fontSize: 12, color: '#B45309' }} /> },
  off_shift:     { label: 'Off shift',     color: '#475569', bg: '#F1F5F9', border: '#CBD5E1', icon: <NightlightIcon   style={{ fontSize: 12, color: '#475569' }} /> },
  at_capacity:   { label: 'At capacity',   color: '#DC2626', bg: '#FEE2E2', border: '#FCA5A5', icon: <BlockIcon        style={{ fontSize: 12, color: '#DC2626' }} /> },
  over_capacity: { label: 'Over capacity', color: '#991B1B', bg: '#FEE2E2', border: '#EF4444', icon: <BlockIcon        style={{ fontSize: 12, color: '#991B1B' }} /> },
}

interface Props {
  status: AvailStatus
  size?: 'small' | 'medium'
  showDot?: boolean
}

export function AvailabilityBadge({ status, size = 'small', showDot = true }: Props) {
  const cfg = STATUS_CONFIG[status]
  return (
    <Chip
      size={size}
      icon={showDot ? cfg.icon : undefined}
      label={cfg.label}
      style={{
        backgroundColor: cfg.bg,
        color: cfg.color,
        border: `1px solid ${cfg.border}`,
        fontWeight: 700,
        fontSize: size === 'small' ? '0.72rem' : '0.8rem',
      }}
      aria-label={`Availability: ${cfg.label}`}
    />
  )
}

/** Compact dot-only version for use inside dropdowns / tables */
export function AvailabilityDot({ status }: { status: AvailStatus }) {
  const cfg = STATUS_CONFIG[status]
  return (
    <Tooltip title={cfg.label} arrow>
      <Box component="span" display="inline-flex" alignItems="center" aria-label={cfg.label}>
        <CircleIcon style={{ fontSize: 10, color: cfg.color, marginRight: 4 }} />
      </Box>
    </Tooltip>
  )
}
