import React, { useState, useEffect } from 'react'
import { Box, Fab, ThemeProvider, LinearProgress, Typography, Button } from '@mui/material'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import SupportAgentIcon from '@mui/icons-material/SupportAgent'
import axios from 'axios'
import Sidebar from './Sidebar'
import Header from './Header'
import ChatbotDrawer from '../ChatbotDrawer'
import { getAppTheme } from '../../theme'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  const ROLE_USERS: Record<string, { id: number; name: string; email: string; role: string }> = {
    employee: { id: 5, name: 'Alice Employee', email: 'alice@company.com', role: 'employee' },
    agent: { id: 3, name: 'Sarah Agent', email: 'agent@helpdesk.com', role: 'agent' },
    manager: { id: 2, name: 'John Manager', email: 'manager@helpdesk.com', role: 'manager' },
  }

  const DEMO_AGENTS: Record<string, { id: number; name: string; email: string; role: string }> = {
    Ravi: { id: 101, name: 'Ravi', email: 'ravi@smartdesk.com', role: 'agent' },
    Priya: { id: 102, name: 'Priya', email: 'priya@smartdesk.com', role: 'agent' },
    Arun: { id: 103, name: 'Arun', email: 'arun@smartdesk.com', role: 'agent' },
    Meena: { id: 104, name: 'Meena', email: 'meena@smartdesk.com', role: 'agent' },
    Kiran: { id: 105, name: 'Kiran', email: 'kiran@smartdesk.com', role: 'agent' },
    'Sarah Agent': { id: 3, name: 'Sarah Agent', email: 'agent@helpdesk.com', role: 'agent' },
    'Mike Network Agent': { id: 4, name: 'Mike Network Agent', email: 'mike.agent@helpdesk.com', role: 'agent' },
  }

  const getInitialRole = () => {
    const storedUser = localStorage.getItem('user')
    if (storedUser) {
      try {
        const u = JSON.parse(storedUser)
        if (u.role) return u.role
      } catch (e) {}
    }
    return 'employee'
  }

  const [currentRole, setCurrentRole] = useState<string>(getInitialRole())
  const [viewingAsAgent, setViewingAsAgent] = useState<string | null>(localStorage.getItem('viewing_as_agent'))
  const [isDemoMode, setIsDemoMode] = useState<boolean>(localStorage.getItem('demo_mode') === 'true')
  const [darkMode, setDarkMode] = useState<boolean>(false)
  const [chatbotOpen, setChatbotOpen] = useState(false)
  const [isSwitching, setIsSwitching] = useState(false)

  const activeTheme = getAppTheme(darkMode ? 'dark' : 'light')

  useEffect(() => {
    const updateDemoState = () => {
      setIsDemoMode(localStorage.getItem('demo_mode') === 'true')
      setViewingAsAgent(localStorage.getItem('viewing_as_agent'))
    }
    window.addEventListener('demo_mode_changed', updateDemoState)
    window.addEventListener('storage', updateDemoState)
    return () => {
      window.removeEventListener('demo_mode_changed', updateDemoState)
      window.removeEventListener('storage', updateDemoState)
    }
  }, [])

  useEffect(() => {
    // Ensure localStorage user identity matches current role if not viewing as agent
    const storedUser = localStorage.getItem('user')
    if (!storedUser && !viewingAsAgent) {
      localStorage.setItem('user', JSON.stringify(ROLE_USERS[currentRole] || ROLE_USERS['employee']))
    }
  }, [currentRole, viewingAsAgent])

  useEffect(() => {
    // Enforce role-based portal separation
    if (currentRole === 'employee') {
      if (location.pathname === '/agent-portal' || location.pathname === '/analytics') {
        navigate('/tickets', { replace: true })
      }
    }
  }, [currentRole, location.pathname])

  const handleRoleSwitch = (newRole: string) => {
    setIsSwitching(true)
    if (viewingAsAgent) {
      setViewingAsAgent(null)
      localStorage.removeItem('viewing_as_agent')
    }
    setCurrentRole(newRole)
    const roleUser = ROLE_USERS[newRole] || { id: 3, name: 'Sarah Agent', email: 'agent@helpdesk.com', role: newRole }
    localStorage.setItem('user', JSON.stringify(roleUser))
    if (!viewingAsAgent) {
      localStorage.setItem('real_role', newRole)
    }
    setTimeout(() => setIsSwitching(false), 400)
  }

  const handleViewAsAgent = async (agentName: string) => {
    try {
      const res = await axios.post(`${API_BASE}/availability/view-as`, { agent_name: agentName }, {
        headers: {
          'X-User-Role': 'manager',
          'X-Real-User-Role': 'manager',
          'X-Demo-Mode': 'true',
        }
      })
      const ag = res.data?.agent || DEMO_AGENTS[agentName]
      setViewingAsAgent(agentName)
      setCurrentRole('agent')
      localStorage.setItem('viewing_as_agent', agentName)
      localStorage.setItem('real_role', 'manager')
      localStorage.setItem('user', JSON.stringify(ag))
      window.dispatchEvent(new CustomEvent('view_as_changed', { detail: agentName }))
      navigate('/agent-portal')
    } catch (e: any) {
      const ag = DEMO_AGENTS[agentName] || { id: 999, name: agentName, email: `${agentName.toLowerCase()}@helpdesk.local`, role: 'agent' }
      setViewingAsAgent(agentName)
      setCurrentRole('agent')
      localStorage.setItem('viewing_as_agent', agentName)
      localStorage.setItem('real_role', 'manager')
      localStorage.setItem('user', JSON.stringify(ag))
      window.dispatchEvent(new CustomEvent('view_as_changed', { detail: agentName }))
      navigate('/agent-portal')
    }
  }

  const handleExitViewAs = () => {
    setViewingAsAgent(null)
    setCurrentRole('agent')
    localStorage.removeItem('viewing_as_agent')
    localStorage.setItem('user', JSON.stringify(ROLE_USERS['agent']))
    window.dispatchEvent(new CustomEvent('view_as_changed', { detail: null }))
    navigate('/agent-portal')
  }

  const handleOpenCreateTicketFromBot = () => {
    navigate('/tickets/create')
  }

  const isRealManager = (localStorage.getItem('real_role') || currentRole) === 'manager' || viewingAsAgent !== null

  return (
    <ThemeProvider theme={activeTheme}>
      <Box display="flex" minHeight="100vh" bgcolor="background.default" color="text.primary">
        <Sidebar currentRole={currentRole} viewingAsAgent={viewingAsAgent} />
        <Box display="flex" flexDirection="column" flexGrow={1} minWidth={0}>
          <Header
            currentRole={currentRole}
            onRoleSwitch={handleRoleSwitch}
            onToggleChatbot={() => setChatbotOpen(!chatbotOpen)}
            darkMode={darkMode}
            onToggleDarkMode={() => setDarkMode(!darkMode)}
            isSwitching={isSwitching}
            isDemoMode={isDemoMode}
            viewingAsAgent={viewingAsAgent}
            isRealManager={isRealManager}
            onViewAsAgent={handleViewAsAgent}
            onExitViewAs={handleExitViewAs}
          />

          {/* Viewing as Agent Banner (Phase 4B Requirement 2) */}
          {viewingAsAgent && (
            <Box
              sx={{
                bgcolor: '#1E40AF',
                color: '#FFFFFF',
                px: 3,
                py: 1.25,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                boxShadow: 2,
              }}
            >
              <Box display="flex" alignItems="center" gap={1.5}>
                <SupportAgentIcon sx={{ fontSize: 20 }} />
                <Typography variant="body2" fontWeight={700}>
                  Viewing as {viewingAsAgent}
                </Typography>
              </Box>
              <Button
                size="small"
                variant="contained"
                onClick={handleExitViewAs}
                sx={{
                  bgcolor: '#EF4444',
                  color: '#FFFFFF',
                  fontWeight: 700,
                  '&:hover': { bgcolor: '#DC2626' },
                  height: 28,
                  px: 2,
                  textTransform: 'none',
                }}
              >
                Exit
              </Button>
            </Box>
          )}

          {/* Thin loading bar under the header during role switch */}
          {isSwitching && (
            <LinearProgress
              sx={{ height: 2, bgcolor: 'transparent' }}
              color="primary"
            />
          )}
          <Box component="main" flexGrow={1} p={3.5} overflow="auto">
            <Outlet context={{ currentRole, viewingAsAgent }} />
          </Box>
        </Box>

        {/* Floating Chatbot Action Button */}
        <Fab
          color="primary"
          aria-label="AI Chatbot"
          onClick={() => setChatbotOpen(true)}
          sx={{
            position: 'fixed',
            bottom: 28,
            right: 28,
            backgroundColor: '#2563EB',
            '&:hover': { backgroundColor: '#1D4ED8' },
            boxShadow: '0 6px 18px rgba(37, 99, 235, 0.35)',
          }}
        >
          <SmartToyIcon />
        </Fab>

        {/* Persistent Chatbot Drawer */}
        <ChatbotDrawer
          open={chatbotOpen}
          onClose={() => setChatbotOpen(false)}
          onOpenCreateTicket={handleOpenCreateTicketFromBot}
        />
      </Box>
    </ThemeProvider>
  )
}
