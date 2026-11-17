import React from 'react'
import { Chip } from '@mui/material'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import { normalizeStatus } from '../../utils/status'

interface PriorityBadgeProps {
  priority: string
  size?: 'small' | 'medium'
}

export function PriorityBadge({ priority, size = 'small' }: PriorityBadgeProps) {
  const p = (priority || 'Medium').toLowerCase()

  if (p === 'critical') {
    return (
      <Chip
        label="CRITICAL"
        size={size}
        style={{ backgroundColor: '#FEE2E2', color: '#DC2626', border: '1px solid #FCA5A5', fontWeight: 700 }}
      />
    )
  }
  if (p === 'high') {
    return (
      <Chip
        label="HIGH"
        size={size}
        style={{ backgroundColor: '#FFEDD5', color: '#D97706', border: '1px solid #FDBA74', fontWeight: 700 }}
      />
    )
  }
  if (p === 'medium') {
    return (
      <Chip
        label="MEDIUM"
        size={size}
        style={{ backgroundColor: '#FEF3C7', color: '#B45309', border: '1px solid #FDE68A', fontWeight: 700 }}
      />
    )
  }
  return (
    <Chip
      label="LOW"
      size={size}
      style={{ backgroundColor: '#D1FAE5', color: '#059669', border: '1px solid #6EE7B7', fontWeight: 700 }}
    />
  )
}

interface SLABadgeProps {
  badge: string
  size?: 'small' | 'medium'
}

export function SLABadge({ badge, size = 'small' }: SLABadgeProps) {
  if (badge === 'RESOLVED' || badge === 'COMPLETED') {
    return (
      <Chip
        label="COMPLETED"
        size={size}
        icon={<CheckCircleOutlineIcon style={{ color: '#047857', fontSize: 14 }} />}
        style={{ backgroundColor: '#ECFDF5', color: '#047857', border: '1px solid #A7F3D0', fontWeight: 700 }}
      />
    )
  }
  if (badge === 'BREACHED') {
    return (
      <Chip
        label="SLA BREACHED"
        size={size}
        icon={<WarningAmberIcon style={{ color: '#FFFFFF', fontSize: 14 }} />}
        style={{ backgroundColor: '#DC2626', color: '#FFFFFF', fontWeight: 800 }}
      />
    )
  }
  if (badge === 'AT_RISK') {
    return (
      <Chip
        label="SLA AT RISK"
        size={size}
        icon={<AccessTimeIcon style={{ color: '#FFFFFF', fontSize: 14 }} />}
        style={{ backgroundColor: '#D97706', color: '#FFFFFF', fontWeight: 700 }}
      />
    )
  }
  return (
    <Chip
      label="ON TRACK"
      size={size}
      icon={<CheckCircleOutlineIcon style={{ color: '#FFFFFF', fontSize: 14 }} />}
      style={{ backgroundColor: '#059669', color: '#FFFFFF', fontWeight: 700 }}
    />
  )
}


interface StatusBadgeProps {
  status: string
  size?: 'small' | 'medium'
}

export function StatusBadge({ status, size = 'small' }: StatusBadgeProps) {
  const s = normalizeStatus(status)
  if (s === 'resolved' || s === 'closed') {
    return (
      <Chip
        label={s.toUpperCase()}
        size={size}
        style={{ backgroundColor: '#ECFDF5', color: '#047857', border: '1px solid #A7F3D0', fontWeight: 600 }}
      />
    )
  }
  if (s === 'in_progress') {
    return (
      <Chip
        label="IN PROGRESS"
        size={size}
        style={{ backgroundColor: '#E0E7FF', color: '#4338CA', border: '1px solid #C7D2FE', fontWeight: 600 }}
      />
    )
  }
  if (s === 'pending_user') {
    return (
      <Chip
        label="PENDING USER"
        size={size}
        style={{ backgroundColor: '#FEF3C7', color: '#B45309', border: '1px solid #FDE68A', fontWeight: 600 }}
      />
    )
  }
  return (
    <Chip
      label="OPEN"
      size={size}
      style={{ backgroundColor: '#DBEAFE', color: '#1D4ED8', border: '1px solid #BFDBFE', fontWeight: 600 }}
    />
  )
}
