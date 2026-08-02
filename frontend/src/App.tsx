import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import DashboardPage from './pages/DashboardPage'
import TicketsPage from './pages/TicketsPage'
import CreateTicketPage from './pages/CreateTicketPage'
import ChatbotPage from './pages/ChatbotPage'
import AnalyticsPage from './pages/AnalyticsPage'
import AgentPortalPage from './pages/AgentPortalPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/tickets" element={<TicketsPage />} />
        <Route path="/tickets/create" element={<CreateTicketPage />} />
        <Route path="/agent-portal" element={<AgentPortalPage />} />
        <Route path="/chatbot" element={<ChatbotPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
