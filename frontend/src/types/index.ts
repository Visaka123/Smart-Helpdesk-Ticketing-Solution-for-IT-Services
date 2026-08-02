export interface User {
  id: string
  email: string
  name: string
  role: string
  token: string
}

export interface AuthState {
  user: User | null
  loading: boolean
  error: string | null
}

export interface Ticket {
  id: string
  title: string
  description: string
  status: string
  priority: string
  predicted_team: string
  predicted_priority: string
  ai_routed: boolean
  kb_match: boolean
  created_at: string
  updated_at: string
}

export interface TicketStats {
  total_tickets: number
  open_tickets: number
  closed_tickets: number
  high_priority: number
  ai_routed: number
  kb_matches: number
  tickets_by_team: Record<string, number>
  tickets_by_priority: Record<string, number>
  tickets_by_status: Record<string, number>
  recent_tickets: Ticket[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  similar_tickets?: Ticket[]
  confidence?: number
  suggested_actions?: string[]
}

export interface ChatbotResponse {
  answer: string
  similar_tickets: Ticket[]
  confidence?: number
  suggested_actions?: string[]
}

export interface CreateTicketPayload {
  title: string
  description: string
}

export interface CreateTicketResponse {
  ticket: Ticket
  predicted_team: string
  predicted_priority: string
  status: string
}
