import apiClient from './client'
import type {
  CreateTicketPayload,
  CreateTicketResponse,
  Ticket,
  TicketStats,
  ChatbotResponse,
  AgentAvailability,
  AssignmentLogEntry,
  LeaveRequest,
  AgentShift,
  OnCallEntry,
  PublicHoliday,
  SyncStatus,
} from '../types'

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post('/auth/login', { email, password }),
  register: (name: string, email: string, password: string) =>
    apiClient.post('/auth/register', { name, email, password }),
}

export const ticketApi = {
  create: (payload: CreateTicketPayload) =>
    apiClient.post<CreateTicketResponse>('/ticket/create', payload),
  getAll: () => apiClient.get<Ticket[]>('/ticket/all'),
  getStats: () => apiClient.get<TicketStats>('/ticket/stats'),
}

export const chatbotApi = {
  ask: (message: string) =>
    apiClient.post<ChatbotResponse>('/chatbot/ask', { message }),
}

export const availabilityApi = {
  // Who is available now
  getAvailableNow: (team?: string) =>
    apiClient.get<AgentAvailability[]>('/availability/available-now', { params: team ? { team } : {} }),

  // Assignment log for a ticket
  getAssignmentLog: (ticketId: number) =>
    apiClient.get<AssignmentLogEntry[]>(`/availability/assignment-log/${ticketId}`),

  // Manual override / reassign
  override: (ticketId: number, newAgentName: string, overrideBy: string) =>
    apiClient.post(`/availability/override/${ticketId}`, { new_agent_name: newAgentName, override_by: overrideBy }),

  // Reroute count for leave confirmation
  getRerouteCount: (leaveId: number) =>
    apiClient.get<{ agent_name: string; reroute_count: number }>(`/availability/leave/${leaveId}/reroute-count`),

  // Demo seed
  demoSeed: (reset = false) =>
    apiClient.post('/availability/demo-seed', { reset }),

  // View as agent
  viewAs: (agentName: string) =>
    apiClient.post('/availability/view-as', { agent_name: agentName }),

  // Shifts
  getShifts: (agentId?: number) =>
    apiClient.get<AgentShift[]>('/availability/shifts', { params: agentId ? { agent_id: agentId } : {} }),
  createShift: (payload: { agent_id: number; weekday: number; start_time: string; end_time: string }) =>
    apiClient.post('/availability/shifts', payload),
  deleteShift: (shiftId: number) =>
    apiClient.delete(`/availability/shifts/${shiftId}`),

  // Leave
  getLeave: (agentId?: number, status?: string) =>
    apiClient.get<LeaveRequest[]>('/availability/leave', { params: { ...(agentId ? { agent_id: agentId } : {}), ...(status ? { status } : {}) } }),
  createLeave: (payload: { agent_id: number; start_datetime: string; end_datetime: string; leave_type: string; notes?: string }) =>
    apiClient.post('/availability/leave', payload),
  approveLeave: (leaveId: number, status: 'approved' | 'cancelled', approvedBy: string) =>
    apiClient.patch(`/availability/leave/${leaveId}/approve`, { status, approved_by: approvedBy }),

  // On-call
  getOnCall: (teamName?: string) =>
    apiClient.get<OnCallEntry[]>('/availability/oncall', { params: teamName ? { team_name: teamName } : {} }),
  createOnCall: (payload: { agent_id: number; team_name: string; start_dt: string; end_dt: string }) =>
    apiClient.post('/availability/oncall', payload),

  // Holidays
  getHolidays: () => apiClient.get<PublicHoliday[]>('/availability/holidays'),
  createHoliday: (payload: { date: string; name: string; region?: string }) =>
    apiClient.post('/availability/holidays', payload),

  // HR Leave Sync
  getSyncStatus: () => apiClient.get<SyncStatus>('/availability/sync-status'),
  syncNow: () => apiClient.post('/availability/sync-now'),
  uploadCsv: (csv_content: string) => apiClient.post('/availability/upload-csv', { csv_content }),
  emergencyUnavailable: () => apiClient.post('/availability/emergency-unavailable'),
}
