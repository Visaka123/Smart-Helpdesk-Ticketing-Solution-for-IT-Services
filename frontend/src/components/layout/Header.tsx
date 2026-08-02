import React from 'react'
import { AppBar, Toolbar, Typography, Box, Chip, Button, IconButton, Tooltip, useTheme } from '@mui/material'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import AccountCircleIcon from '@mui/icons-material/AccountCircle'
import SwapHorizIcon from '@mui/icons-material/SwapHoriz'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'

interface HeaderProps {
  currentRole: string
  onRoleSwitch: (role: string) => void
  onToggleChatbot: () => void
  darkMode: boolean
  onToggleDarkMode: () => void
}

export default function Header({ currentRole, onRoleSwitch, onToggleChatbot, darkMode, onToggleDarkMode }: HeaderProps) {
  const theme = useTheme()

  const getRoleLabel = () => {
    if (currentRole === 'agent') return 'Support Agent'
    if (currentRole === 'manager') return 'Team Manager'
    return 'Employee (User)'
  }

  const cycleRole = () => {
    if (currentRole === 'employee') onRoleSwitch('agent')
    else if (currentRole === 'agent') onRoleSwitch('manager')
    else onRoleSwitch('employee')
  }

  return (
    <AppBar position="sticky" style={{ backgroundColor: theme.palette.background.paper }}>
      <Toolbar style={{ justifyContent: 'space-between' }}>
        <Box display="flex" alignItems="center" gap={2}>
          <Typography variant="h6" fontWeight={800} style={{ color: '#2563EB', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ backgroundColor: '#2563EB', color: '#FFF', padding: '3px 10px', borderRadius: 6, fontSize: '0.85rem', fontWeight: 800 }}>
              ENTERPRISE
            </span>
            SMART HELPDESK AI
          </Typography>
          <Chip
            label={getRoleLabel()}
            size="small"
            icon={<AccountCircleIcon style={{ color: '#2563EB' }} />}
            style={{ fontWeight: 700, backgroundColor: darkMode ? '#1E293B' : '#EFF6FF', color: '#2563EB', border: '1px solid #BFDBFE' }}
          />
        </Box>

        <Box display="flex" alignItems="center" gap={1.5}>
          <Tooltip title={darkMode ? 'Switch to Light Mode' : 'Switch to Graphite Dark Mode'}>
            <IconButton onClick={onToggleDarkMode} size="small" style={{ color: theme.palette.text.secondary }}>
              {darkMode ? <LightModeIcon fontSize="small" /> : <DarkModeIcon fontSize="small" />}
            </IconButton>
          </Tooltip>

          <Tooltip title="Click to cycle role (Employee -> Agent -> Manager)">
            <Button
              variant="outlined"
              size="small"
              startIcon={<SwapHorizIcon />}
              onClick={cycleRole}
              style={{ borderColor: theme.palette.divider, color: theme.palette.text.primary }}
            >
              Switch Role
            </Button>
          </Tooltip>

          <Button
            variant="contained"
            color="primary"
            size="small"
            startIcon={<SmartToyIcon />}
            onClick={onToggleChatbot}
            style={{ backgroundColor: '#2563EB' }}
          >
            AI Assistant
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  )
}
