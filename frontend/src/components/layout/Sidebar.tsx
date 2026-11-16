import React from 'react'
import { Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Box, Divider, Typography, useTheme } from '@mui/material'
import { useNavigate, useLocation } from 'react-router-dom'
import DashboardIcon from '@mui/icons-material/Dashboard'
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber'
import AddCircleIcon from '@mui/icons-material/AddCircle'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import SupportAgentIcon from '@mui/icons-material/SupportAgent'
import AssessmentIcon from '@mui/icons-material/Assessment'
import BeachAccessIcon from '@mui/icons-material/BeachAccess'
import ScheduleIcon from '@mui/icons-material/Schedule'

const drawerWidth = 240

interface SidebarProps {
  currentRole: string
  viewingAsAgent?: string | null
}

export default function Sidebar({ currentRole, viewingAsAgent }: SidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const theme = useTheme()

  const effectiveRole = viewingAsAgent ? 'agent' : currentRole

  const navItems = [
    { label: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard', roles: ['employee', 'agent', 'manager'] },
    { label: 'Create Ticket', icon: <AddCircleIcon />, path: '/tickets/create', roles: ['employee', 'agent', 'manager'] },
    { label: effectiveRole === 'employee' ? 'My Tickets' : 'All Tickets', icon: <ConfirmationNumberIcon />, path: '/tickets', roles: ['employee', 'agent', 'manager'] },
    { label: 'Agent Workspace', icon: <SupportAgentIcon />, path: '/agent-portal', roles: ['agent', 'manager'] },
    { label: 'RAG Chatbot', icon: <SmartToyIcon />, path: '/chatbot', roles: ['employee', 'agent', 'manager'] },
    { label: 'SLA Analytics', icon: <AssessmentIcon />, path: '/analytics', roles: ['manager', 'agent'] },
    { label: 'Leave Requests', icon: <BeachAccessIcon />, path: '/leave', roles: ['agent', 'manager'] },
    { label: 'Shifts & On-Call', icon: <ScheduleIcon />, path: '/shifts', roles: ['manager'] },
  ]

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: drawerWidth,
          boxSizing: 'border-box',
          backgroundColor: theme.palette.mode === 'light' ? '#FFFFFF' : '#0F172A',
          borderRight: `1px solid ${theme.palette.divider}`,
        },
      }}
    >
      <Box p={2.5} textAlign="center">
        <Typography variant="caption" style={{ color: '#2563EB', fontWeight: 800, letterSpacing: '0.08em' }}>
          SMART DESK ENTERPRISE
        </Typography>
      </Box>
      <Divider style={{ borderColor: theme.palette.divider }} />
      <List>
        {navItems
          .filter((item) => item.roles.includes(effectiveRole))
          .map((item) => {
            const isActive = location.pathname === item.path
            return (
              <ListItem key={item.path} disablePadding sx={{ mb: 0.5 }}>
                <ListItemButton
                  onClick={() => navigate(item.path)}
                  sx={{
                    borderRadius: 1.5,
                    mx: 1,
                    backgroundColor: isActive ? (theme.palette.mode === 'light' ? '#EFF6FF' : 'rgba(37, 99, 235, 0.2)') : 'transparent',
                    borderLeft: isActive ? '3px solid #2563EB' : '3px solid transparent',
                    '&:hover': {
                      backgroundColor: theme.palette.mode === 'light' ? '#F1F5F9' : 'rgba(255, 255, 255, 0.05)',
                    },
                  }}
                >
                  <ListItemIcon sx={{ color: isActive ? '#2563EB' : theme.palette.text.secondary, minWidth: 38 }}>
                    {item.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={item.label}
                    primaryTypographyProps={{
                      fontSize: '0.875rem',
                      fontWeight: isActive ? 700 : 500,
                      color: isActive ? '#2563EB' : theme.palette.text.primary,
                    }}
                  />
                </ListItemButton>
              </ListItem>
            )
          })}
      </List>
    </Drawer>
  )
}
