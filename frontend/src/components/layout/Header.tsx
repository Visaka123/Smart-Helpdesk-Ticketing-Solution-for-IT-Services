import React from 'react'
import { AppBar, Toolbar, Typography, Box, Chip, Button, IconButton, Tooltip, CircularProgress, useTheme, FormControl, InputLabel, Select, MenuItem } from '@mui/material'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import AccountCircleIcon from '@mui/icons-material/AccountCircle'
import SwapHorizIcon from '@mui/icons-material/SwapHoriz'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'
import VisibilityIcon from '@mui/icons-material/Visibility'

interface HeaderProps {
  currentRole: string
  onRoleSwitch: (role: string) => void
  onToggleChatbot: () => void
  darkMode: boolean
  onToggleDarkMode: () => void
  isSwitching?: boolean
  isDemoMode?: boolean
  viewingAsAgent?: string | null
  isRealManager?: boolean
  onViewAsAgent?: (agentName: string) => void
  onExitViewAs?: () => void
}

export default function Header({
  currentRole,
  onRoleSwitch,
  onToggleChatbot,
  darkMode,
  onToggleDarkMode,
  isSwitching,
  isDemoMode,
  viewingAsAgent,
  isRealManager,
  onViewAsAgent,
  onExitViewAs,
}: HeaderProps) {
  const theme = useTheme()

  const getRoleLabel = () => {
    if (viewingAsAgent) return `Agent (${viewingAsAgent})`
    if (currentRole === 'agent') return 'Support Agent'
    if (currentRole === 'manager') return 'Team Manager'
    return 'Employee (User)'
  }

  const cycleRole = () => {
    if (viewingAsAgent && onExitViewAs) {
      onExitViewAs()
      return
    }
    if (currentRole === 'employee') onRoleSwitch('agent')
    else if (currentRole === 'agent') onRoleSwitch('manager')
    else onRoleSwitch('employee')
  }

  const showViewAs = currentRole === 'agent' || Boolean(viewingAsAgent)

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
          {/* View as agent dropdown - visible only in Support Agent view */}
          {showViewAs && (
            <Tooltip title="Select an agent to view workspace">
              <span>
                <FormControl size="small" sx={{ minWidth: 160 }}>
                  <InputLabel id="view-as-label" sx={{ fontSize: '0.8rem' }}>View as agent</InputLabel>
                  <Select
                    labelId="view-as-label"
                    label="View as agent"
                    value={viewingAsAgent || ''}
                    onChange={(e) => {
                      if (e.target.value) onViewAsAgent?.(e.target.value)
                    }}
                    sx={{ height: 32, fontSize: '0.8rem' }}
                  >
                    <MenuItem value="" disabled>Select Agent</MenuItem>
                    <MenuItem value="Ravi">Ravi</MenuItem>
                    <MenuItem value="Priya">Priya</MenuItem>
                    <MenuItem value="Arun">Arun</MenuItem>
                    <MenuItem value="Meena">Meena</MenuItem>
                    <MenuItem value="Kiran">Kiran</MenuItem>
                    <MenuItem value="Sarah Agent">Sarah Agent</MenuItem>
                    <MenuItem value="Mike Network Agent">Mike Network Agent</MenuItem>
                  </Select>
                </FormControl>
              </span>
            </Tooltip>
          )}

          <Tooltip title={darkMode ? 'Switch to Light Mode' : 'Switch to Graphite Dark Mode'}>
            <IconButton onClick={onToggleDarkMode} size="small" style={{ color: theme.palette.text.secondary }}>
              {darkMode ? <LightModeIcon fontSize="small" /> : <DarkModeIcon fontSize="small" />}
            </IconButton>
          </Tooltip>

          <Tooltip title="Click to cycle role (Employee → Agent → Manager)">
            <span>
              <Button
                variant="outlined"
                size="small"
                startIcon={
                  isSwitching
                    ? <CircularProgress size={14} color="inherit" />
                    : <SwapHorizIcon />
                }
                onClick={cycleRole}
                disabled={isSwitching}
                style={{ borderColor: theme.palette.divider, color: theme.palette.text.primary, minWidth: 120 }}
              >
                {isSwitching ? 'Switching…' : 'Switch Role'}
              </Button>
            </span>
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
