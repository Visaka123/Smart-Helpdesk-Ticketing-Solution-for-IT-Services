import apiClient from './client'
import type {
  CreateTicketPayload,
  CreateTicketResponse,
  Ticket,
  TicketStats,
  ChatbotResponse,
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
