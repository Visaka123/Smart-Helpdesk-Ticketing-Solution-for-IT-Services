import React from 'react'
import { Box, Typography, Paper, Avatar, Chip, useTheme } from '@mui/material'
import ForumIcon from '@mui/icons-material/Forum'
import LockIcon from '@mui/icons-material/Lock'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import SwapHorizIcon from '@mui/icons-material/SwapHoriz'
import WarningIcon from '@mui/icons-material/Warning'
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh'

interface CommentItem {
  id: number
  author_name: string
  author_role: string
  content: string
  is_internal: boolean
  created_at: string
}

interface ITSMTimelineProps {
  comments: CommentItem[]
}

export function ITSMTimeline({ comments }: ITSMTimelineProps) {
  const theme = useTheme()

  if (!comments || comments.length === 0) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'background.paper', border: '1px dashed', borderColor: 'divider' }}>
        <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>
          No conversation or audit entries recorded yet.
        </Typography>
      </Paper>
    )
  }

  const getBadgeConfig = (c: CommentItem) => {
    const text = c.content.toLowerCase()
    if (c.is_internal) {
      return {
        label: 'INTERNAL NOTE',
        bgColor: '#FEF3C7',
        color: '#B45309',
        borderColor: '#FDE68A',
        icon: <LockIcon style={{ fontSize: 13 }} />,
      }
    }
    if (text.includes('resolved') || text.includes('resolution')) {
      return {
        label: 'RESOLUTION',
        bgColor: '#D1FAE5',
        color: '#059669',
        borderColor: '#6EE7B7',
        icon: <CheckCircleIcon style={{ fontSize: 13 }} />,
      }
    }
    if (text.includes('assigned team') || text.includes('re-routed')) {
      return {
        label: 'TEAM ASSIGNMENT',
        bgColor: '#E0E7FF',
        color: '#4338CA',
        borderColor: '#C7D2FE',
        icon: <SwapHorizIcon style={{ fontSize: 13 }} />,
      }
    }
    if (text.includes('sla') || text.includes('breached') || text.includes('triage')) {
      return {
        label: 'SYSTEM EVENT',
        bgColor: '#FEE2E2',
        color: '#DC2626',
        borderColor: '#FCA5A5',
        icon: <WarningIcon style={{ fontSize: 13 }} />,
      }
    }
    if (c.author_role === 'system' || c.author_name.includes('AI')) {
      return {
        label: 'AI ROUTER',
        bgColor: '#F3E8FF',
        color: '#6B21A8',
        borderColor: '#E9D5FF',
        icon: <AutoFixHighIcon style={{ fontSize: 13 }} />,
      }
    }
    return {
      label: 'PUBLIC REPLY',
      bgColor: theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B',
      color: '#2563EB',
      borderColor: '#BFDBFE',
      icon: <ForumIcon style={{ fontSize: 13 }} />,
    }
  }

  return (
    <Box display="flex" flexDirection="column" gap={1.5}>
      {comments.map((c) => {
        const badge = getBadgeConfig(c)
        const initial = (c.author_name || 'U')[0].toUpperCase()

        return (
          <Paper
            key={c.id}
            sx={{
              p: 2,
              bgcolor: c.is_internal ? (theme.palette.mode === 'light' ? '#FFFBEB' : '#1E1B18') : 'background.paper',
              border: `1px solid ${badge.borderColor}`,
              borderRadius: 2,
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.04)',
            }}
          >
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
              <Box display="flex" alignItems="center" gap={1.2}>
                <Avatar sx={{ width: 26, height: 26, fontSize: '0.78rem', bgcolor: badge.color, fontWeight: 700 }}>
                  {initial}
                </Avatar>
                <Typography variant="subtitle2" fontWeight={700} style={{ color: theme.palette.text.primary }}>
                  {c.author_name}
                </Typography>
                <Chip
                  icon={badge.icon}
                  label={badge.label}
                  size="small"
                  style={{
                    backgroundColor: badge.bgColor,
                    color: badge.color,
                    fontWeight: 700,
                    fontSize: '0.7rem',
                    height: 22,
                  }}
                />
              </Box>
              <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                {c.created_at}
              </Typography>
            </Box>

            <Typography variant="body2" style={{ color: theme.palette.text.primary, whiteSpace: 'pre-line', lineHeight: 1.5 }}>
              {c.content}
            </Typography>
          </Paper>
        )
      })}
    </Box>
  )
}
