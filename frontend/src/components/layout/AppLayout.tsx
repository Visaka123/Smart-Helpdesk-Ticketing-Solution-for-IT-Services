import React, { useState, useEffect } from 'react'
import { Box, Fab, ThemeProvider } from '@mui/material'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import Sidebar from './Sidebar'
import Header from './Header'
import ChatbotDrawer from '../ChatbotDrawer'
import { getAppTheme } from '../../theme'

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  
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
  const [darkMode, setDarkMode] = useState<boolean>(false)
  const [chatbotOpen, setChatbotOpen] = useState(false)

  const activeTheme = getAppTheme(darkMode ? 'dark' : 'light')

  useEffect(() => {
    // Enforce role-based portal separation
    if (currentRole === 'employee') {
      if (location.pathname === '/agent-portal' || location.pathname === '/analytics') {
        navigate('/tickets', { replace: true })
      }
    }
  }, [currentRole, location.pathname])

  const handleRoleSwitch = (newRole: string) => {
    setCurrentRole(newRole)
    const storedUser = localStorage.getItem('user')
    if (storedUser) {
      try {
        const u = JSON.parse(storedUser)
        u.role = newRole
        localStorage.setItem('user', JSON.stringify(u))
      } catch (e) {}
    }
  }

  const handleOpenCreateTicketFromBot = () => {
    navigate('/tickets/create')
  }

  return (
    <ThemeProvider theme={activeTheme}>
      <Box display="flex" minHeight="100vh" bgcolor="background.default" color="text.primary">
        <Sidebar currentRole={currentRole} />
        <Box display="flex" flexDirection="column" flexGrow={1} minWidth={0}>
          <Header
            currentRole={currentRole}
            onRoleSwitch={handleRoleSwitch}
            onToggleChatbot={() => setChatbotOpen(!chatbotOpen)}
            darkMode={darkMode}
            onToggleDarkMode={() => setDarkMode(!darkMode)}
          />
          <Box component="main" flexGrow={1} p={3.5} overflow="auto">
            <Outlet context={{ currentRole }} />
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
