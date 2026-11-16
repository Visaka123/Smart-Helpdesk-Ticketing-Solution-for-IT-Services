import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import DashboardPage from './pages/DashboardPage'
import TicketsPage from './pages/TicketsPage'
import TicketDetailPage from './pages/TicketDetailPage'
import CreateTicketPage from './pages/CreateTicketPage'
import ChatbotPage from './pages/ChatbotPage'
import AnalyticsPage from './pages/AnalyticsPage'
import AgentPortalPage from './pages/AgentPortalPage'
import LeavePage from './pages/LeavePage'
import ShiftsPage from './pages/ShiftsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/tickets" element={<TicketsPage />} />
        <Route path="/tickets/create" element={<CreateTicketPage />} />
        <Route path="/tickets/:id" element={<TicketDetailPage />} />
        <Route path="/agent-portal" element={<AgentPortalPage />} />
        <Route path="/chatbot" element={<ChatbotPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/leave" element={<LeavePage />} />
        <Route path="/shifts" element={<ShiftsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
