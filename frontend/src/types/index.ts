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
  assigned_agent_name?: string
  predicted_priority?: string
  sla_hours?: number
  sla_badge?: string
  sla_due_at?: string
  ai_routed?: boolean
  kb_match?: boolean
  created_at: string
  updated_at?: string
  requester_name?: string
  routing_confidence?: number
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

// ── Availability types ────────────────────────────────────────

export type AvailabilityStatus = 'available' | 'on_leave' | 'off_shift' | 'at_capacity'

export interface AgentAvailability {
  id: number
  name: string
  team: string
  timezone: string
  skills: string
  status?: string
  return_date?: string
  shift_end: string | null
  available: boolean
  on_shift: boolean
  on_call: boolean
  on_leave: boolean
  leave_until?: string | null
  leave_source?: string | null
  below_cap: boolean
  open_tickets: number
  ticket_cap: number
}

export interface AssignmentLogEntry {
  id: number
  assigned_to: string | null
  reason: string
  fallback: string | null
  override_by: string | null
  at: string
}

export interface LeaveRequest {
  id: number
  agent_name: string
  start: string
  end: string
  type: string
  status: string
  notes: string | null
  source?: 'hr_sync' | 'manual'
  external_id?: string | null
  last_synced_at?: string | null
}

export interface SyncStatus {
  sync_enabled: boolean
  last_synced_at: string | null
  minutes_since_sync: number | null
  stale: boolean
}

export interface AgentShift {
  id: number
  agent_id: number
  agent_name: string
  weekday: number
  start_time: string
  end_time: string
}

export interface OnCallEntry {
  id: number
  agent_name: string
  team: string
  start: string
  end: string
}

export interface PublicHoliday {
  id: number
  date: string
  name: string
  region: string | null
}
