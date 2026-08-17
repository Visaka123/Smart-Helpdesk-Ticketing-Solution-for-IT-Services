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
  id: any
  title: string
  description: string
  status: string
  priority: string
  category?: string
  assigned_team?: string
  predicted_team?: string
  predicted_priority?: string
  sla_hours?: number
  ai_routed?: boolean
  kb_match?: boolean
  created_at: string
  updated_at?: string
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

export interface SourceItem {
  id: number
  title: string
  document_type: string
  source_type?: 'internal_kb' | 'external_web'
  category: string
  snippet: string
  source_file: string
  download_url: string
  domain?: string
  relevance_pct?: number
  similarity_score?: number
  relevance_label?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  sources?: SourceItem[]
  similar_tickets?: Ticket[]
  confidence?: number
  suggested_actions?: string[]
  error?: boolean
}

export interface ChatbotResponse {
  answer: string
  sources?: SourceItem[]
  similar_tickets: Ticket[]
  confidence?: number
  suggested_actions?: string[]
  error?: boolean
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
