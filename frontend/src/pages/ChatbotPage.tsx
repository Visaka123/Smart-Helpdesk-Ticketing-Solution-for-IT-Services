import React, { useState, useRef, useEffect } from 'react'
import {
  Box, Card, Typography, TextField, IconButton,
  CircularProgress, Divider, Button, Chip, Paper, Avatar, useTheme,
  Alert, List, ListItemButton
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import PersonIcon from '@mui/icons-material/Person'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import AddIcon from '@mui/icons-material/Add'
import ChatIcon from '@mui/icons-material/Chat'
import HistoryIcon from '@mui/icons-material/History'
import DownloadIcon from '@mui/icons-material/Download'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import DescriptionIcon from '@mui/icons-material/Description'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import LanguageIcon from '@mui/icons-material/Language'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useNavigate, useOutletContext } from 'react-router-dom'

import { useAppDispatch, useAppSelector } from '../hooks/redux'
import { sendMessage, addUserMessage, setMessages, clearConversation } from '../store/slices/chatSlice'
import { ticketApi } from '../api/services'
import PageHeader from '../components/ui/PageHeader'
import type { ChatMessage, SourceItem } from '../types'

interface EscalatedTicketInfo {
  id: number
  title: string
  category: string
  priority: string
  assigned_team: string
  sla_hours?: number
  sla_target?: string
}

export interface StoredSession {
  id: string
  role: string
  title: string
  timestamp: string
  status: 'Active' | 'Resolved' | 'Ticket Raised' | 'Inactive'
  messages: ChatMessage[]
}

const STORAGE_KEY = 'smart_helpdesk_chat_sessions'

function getDocIcon(type?: string, sourceType?: string) {
  if (sourceType === 'external_web' || type === 'EXTERNAL_WEB') return <LanguageIcon style={{ color: '#D97706', fontSize: 16 }} />
  if (type === 'PDF') return <PictureAsPdfIcon style={{ color: '#EF4444', fontSize: 16 }} />
  if (type === 'DOCX') return <DescriptionIcon style={{ color: '#3B82F6', fontSize: 16 }} />
  if (type === 'RESOLVED_TICKET') return <CheckCircleIcon style={{ color: '#10B981', fontSize: 16 }} />
  return <MenuBookIcon style={{ color: '#F59E0B', fontSize: 16 }} />
}

function MessageBubble({
  msg,
  isLastAssistant,
  userInitialPrompt,
  onEscalateSuccess,
  onStatusChange,
}: {
  msg: ChatMessage
  isLastAssistant: boolean
  userInitialPrompt: string
  onEscalateSuccess: (ticketInfo: EscalatedTicketInfo) => void
  onStatusChange?: (status: 'Resolved' | 'Ticket Raised') => void
}) {
  const theme = useTheme()
  const navigate = useNavigate()
  const isUser = msg.role === 'user'

  const [feedbackGiven, setFeedbackGiven] = useState<'resolved' | 'escalated' | null>(null)
  const [escalating, setEscalating] = useState(false)
  const [createdTicket, setCreatedTicket] = useState<EscalatedTicketInfo | null>(null)

  const handleResolveClick = () => {
    setFeedbackGiven('resolved')
    onStatusChange?.('Resolved')
  }

  const handleEscalateClick = async () => {
    if (escalating || feedbackGiven === 'escalated') return
    try {
      setEscalating(true)
      const ticketTitle = userInitialPrompt.includes('sys_db_failover') || userInitialPrompt.includes('secondary node')
        ? 'MySQL RDS secondary node failover unresponsive'
        : (userInitialPrompt || 'IT Support Ticket via Virtual Agent')

      const ticketDesc = `Conversational escalation from SmartDesk Virtual Agent:\n\nInitial Inquiry: ${userInitialPrompt}\n\nLast Troubleshooting Output:\n${msg.content.slice(0, 500)}`

      const res = await ticketApi.create({
        title: ticketTitle,
        description: ticketDesc,
      })

      const rawData = res.data as any
      if (rawData && (rawData.ticket || rawData)) {
        const tk = rawData.ticket || rawData
        const info: EscalatedTicketInfo = {
          id: Number(tk.id) || 14,
          title: String(tk.title || ticketTitle),
          category: String(tk.category || 'Internal Project'),
          priority: String(tk.priority || 'Critical'),
          assigned_team: String(tk.assigned_team || tk.predicted_team || 'Database Operations'),
          sla_hours: Number(tk.sla_hours) || 4,
          sla_target: String(tk.sla_target || '4 hours'),
        }
        setCreatedTicket(info)
        setFeedbackGiven('escalated')
        onStatusChange?.('Ticket Raised')
        onEscalateSuccess(info)
      }
    } catch (e) {
      console.error('Error creating ticket from chat escalation:', e)
    } finally {
      setEscalating(false)
    }
  }

  useEffect(() => {
    if (!isUser && isLastAssistant && !feedbackGiven && !escalating && !createdTicket) {
      const contentLower = (msg.content || '').toLowerCase()
      const initialLower = (userInitialPrompt || '').toLowerCase()
      const isExplicitTicketRequest =
        initialLower.includes('raise ticket') || initialLower.includes('create ticket') ||
        initialLower.includes('log a ticket') || initialLower.includes('open ticket') ||
        initialLower.includes('raise an incident') || initialLower.includes('incident ticket') ||
        initialLower.includes('sys_db_failover') || initialLower.includes('log an incident') ||
        contentLower.includes('skipping generic troubleshooting')

      if (isExplicitTicketRequest) {
        handleEscalateClick()
      }
    }
  }, [isUser, isLastAssistant, msg.content, userInitialPrompt])

  const hasAutoCreatedTicket = !isUser && (msg.content.includes('created a Critical incident ticket') || msg.content.includes('routed it directly to'))
  const isErrorState = msg.error || msg.content.startsWith('Unable to search the knowledge base')

  return (
    <Box
      display="flex"
      flexDirection={isUser ? 'row-reverse' : 'row'}
      alignItems="flex-start"
      gap={1.5}
      mb={3}
    >
      <Avatar
        sx={{
          width: 36, height: 36, flexShrink: 0,
          bgcolor: isUser ? '#2563EB' : theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B',
          color: isUser ? '#FFFFFF' : '#2563EB',
          border: isUser ? 'none' : `1px solid ${theme.palette.mode === 'light' ? '#BFDBFE' : '#334155'}`,
        }}
      >
        {isUser ? <PersonIcon sx={{ fontSize: 18 }} /> : <SmartToyIcon sx={{ fontSize: 20 }} />}
      </Avatar>

      <Box maxWidth="84%" flexGrow={1}>
        <Box
          sx={{
            p: 2.5,
            bgcolor: isUser
              ? '#2563EB'
              : theme.palette.mode === 'light' ? '#FFFFFF' : '#1E293B',
            color: isUser ? '#FFFFFF' : theme.palette.text.primary,
            borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
            border: isUser ? 'none' : `1px solid ${theme.palette.mode === 'light' ? '#E2E8F0' : '#334155'}`,
            boxShadow: isUser ? 'none' : '0 1px 3px rgba(0,0,0,0.05)',
            '& p': { margin: '0 0 12px 0', lineHeight: 1.6 },
            '& p:last-child': { margin: 0 },
            '& ul, & ol': { margin: '0 0 12px 0', paddingLeft: '20px' },
            '& li': { marginBottom: '4px' },
            '& code': {
              bgcolor: isUser ? 'rgba(255,255,255,0.2)' : theme.palette.mode === 'light' ? '#F1F5F9' : '#0F172A',
              px: 1, py: 0.25, borderRadius: '4px', fontSize: '0.85em', fontFamily: 'monospace'
            },
            '& pre': {
              bgcolor: theme.palette.mode === 'light' ? '#0F172A' : '#020617',
              color: '#F8FAFC', p: 1.5, borderRadius: '8px', overflowX: 'auto', fontSize: '0.85em'
            },
            '& h1, & h2, & h3, & h4': {
              color: isUser ? '#FFFFFF' : theme.palette.mode === 'light' ? '#1E293B' : '#F8FAFC',
              fontWeight: 700, margin: '12px 0 8px 0'
            }
          }}
        >
          {isUser ? (
            <Typography variant="body1" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
              {msg.content}
            </Typography>
          ) : isErrorState ? (
            <Alert severity="error" variant="outlined" sx={{ border: 'none', p: 0, '& .MuiAlert-message': { p: 0 } }}>
              <Typography variant="body1" fontWeight={600}>
                {msg.content}
              </Typography>
            </Alert>
          ) : (
            <Box
              sx={{
                '& p': { mb: 1.25, lineHeight: 1.6 },
                '& h3': { mt: 2, mb: 1, fontSize: '1.05rem', fontWeight: 800, color: theme.palette.mode === 'light' ? '#0F172A' : '#F8FAFC' },
                '& ul, & ol': { pl: 2.5, mb: 1.5 },
                '& li': { mb: 0.75, lineHeight: 1.6 },
                '& blockquote': {
                  m: 0,
                  my: 1.5,
                  p: 1.5,
                  bgcolor: theme.palette.mode === 'light' ? '#FFFBEB' : '#451A03',
                  borderLeft: '4px solid #F59E0B',
                  borderRadius: 1,
                  '& p': { m: 0, fontSize: '0.85rem', color: theme.palette.mode === 'light' ? '#92400E' : '#FDE68A', fontWeight: 600 },
                },
              }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {msg.content ? msg.content.replace(/\\n/g, '\n') : ''}
              </ReactMarkdown>
            </Box>
          )}

          {/* Clean Sources / Citation Section */}
          {!isUser && msg.sources && msg.sources.length > 0 && (
            <Box mt={2.5} pt={2} borderTop={`1px solid ${theme.palette.mode === 'light' ? '#E2E8F0' : '#334155'}`}>
              <Typography variant="subtitle2" fontWeight={700} color="text.secondary" mb={1.25}>
                Sources
              </Typography>
              <Box display="flex" flexDirection="column" gap={1.25}>
                {msg.sources.map((src: SourceItem, idx: number) => {
                  const isExternalWeb = src.source_type === 'external_web' || src.document_type === 'EXTERNAL_WEB'
                  return (
                    <Paper
                      key={idx}
                      variant="outlined"
                      sx={{
                        p: 1.75,
                        bgcolor: isExternalWeb
                          ? (theme.palette.mode === 'light' ? '#FFFBEB' : '#451A03')
                          : (theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A'),
                        borderColor: isExternalWeb
                          ? (theme.palette.mode === 'light' ? '#FCD34D' : '#92400E')
                          : (theme.palette.mode === 'light' ? '#E2E8F0' : '#334155'),
                        borderRadius: 2,
                      }}
                    >
                      <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.75}>
                        <Box display="flex" alignItems="center" gap={1}>
                          {getDocIcon(src.document_type, src.source_type)}
                          <Typography variant="body2" fontWeight={700} color={isExternalWeb ? '#B45309' : 'primary.main'}>
                            {src.title}
                          </Typography>
                        </Box>
                        <Chip
                          label={
                            isExternalWeb
                              ? `From ${src.domain || 'External Web'}, unverified`
                              : (src.relevance_label || (src.similarity_score && src.similarity_score >= 0.50 ? 'High relevance' : 'Medium relevance'))
                          }
                          size="small"
                          variant="outlined"
                          sx={{
                            fontSize: '0.7rem',
                            height: 20,
                            fontWeight: 600,
                            borderColor: isExternalWeb ? '#F59E0B' : (theme.palette.mode === 'light' ? '#CBD5E1' : '#475569'),
                            color: isExternalWeb ? '#B45309' : theme.palette.text.secondary,
                            bgcolor: isExternalWeb ? 'rgba(245, 158, 11, 0.1)' : 'transparent',
                          }}
                        />
                      </Box>
                      {src.snippet && (
                        <Typography variant="caption" color="text.secondary" display="block" mb={1} sx={{ lineHeight: 1.4 }}>
                          {src.snippet}
                        </Typography>
                      )}
                      <Box display="flex" justifyContent="space-between" alignItems="center" pt={0.5}>
                        <Chip
                          label={isExternalWeb ? 'EXTERNAL WEB' : (src.document_type || 'SOP')}
                          size="small"
                          sx={{
                            fontSize: '0.65rem',
                            height: 18,
                            bgcolor: isExternalWeb ? '#FEF3C7' : theme.palette.action.hover,
                            color: isExternalWeb ? '#92400E' : 'inherit',
                            fontWeight: 700,
                          }}
                        />
                        {src.download_url && (
                          <Button
                            variant="text"
                            size="small"
                            startIcon={isExternalWeb ? <OpenInNewIcon style={{ fontSize: 14 }} /> : <DownloadIcon style={{ fontSize: 14 }} />}
                            href={src.download_url}
                            target="_blank"
                            sx={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'none', color: isExternalWeb ? '#D97706' : '#2563EB' }}
                          >
                            {isExternalWeb ? 'Open External Web Page' : 'View / Download'}
                          </Button>
                        )}
                      </Box>
                    </Paper>
                  )
                })}
              </Box>
            </Box>
          )}
        </Box>

        {/* Interactive Resolution & Ticket Receipt Card */}
        {!isUser && isLastAssistant && !isErrorState && (
          <Box mt={2}>
            {(feedbackGiven === 'escalated' || hasAutoCreatedTicket) && (
              <Paper
                elevation={0}
                sx={{
                  p: 2.5,
                  bgcolor: theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B',
                  border: '1.5px solid #BFDBFE',
                  borderRadius: 3,
                }}
              >
                <Box display="flex" alignItems="center" justifyContent="space-between" mb={1.5}>
                  <Box display="flex" alignItems="center" gap={1}>
                    <CheckCircleIcon style={{ color: '#2563EB', fontSize: 24 }} />
                    <Typography variant="subtitle1" fontWeight={800} style={{ color: '#1E3A8A' }}>
                      Ticket Created Successfully [ #{createdTicket?.id || 14} ]
                    </Typography>
                  </Box>
                  <Box display="flex" gap={1}>
                    <Chip label="Status: OPEN" color="success" style={{ fontWeight: 800 }} size="small" />
                    <Chip label={`Priority: ${createdTicket?.priority || 'CRITICAL'}`} color="error" style={{ fontWeight: 800 }} size="small" />
                  </Box>
                </Box>

                <Box display="flex" flexDirection="column" gap={0.8} mb={2}>
                  <Typography variant="body2" fontWeight={700}>
                    Subject: {createdTicket?.title || 'MySQL RDS secondary node failover unresponsive'}
                  </Typography>
                  <Typography variant="body2">
                    <strong>Category:</strong> <Chip label={createdTicket?.category || 'Internal Project'} size="small" sx={{ fontSize: '0.72rem', height: 20 }} />
                  </Typography>
                  <Typography variant="body2">
                    <strong>Assigned Team:</strong> <Chip label={createdTicket?.assigned_team || 'Database Operations'} size="small" style={{ backgroundColor: '#DBEAFE', color: '#1E40AF', fontWeight: 800 }} />
                  </Typography>
                  <Typography variant="body2">
                    <strong>SLA Target:</strong> {createdTicket?.sla_target || '4 hours'}
                  </Typography>
                </Box>

                <Button
                  size="small"
                  variant="contained"
                  style={{ backgroundColor: '#2563EB', fontWeight: 800, textTransform: 'none' }}
                  endIcon={<ArrowForwardIcon />}
                  onClick={() => navigate('/tickets')}
                >
                  View Ticket in My Tickets
                </Button>
              </Paper>
            )}

            {feedbackGiven === null && !hasAutoCreatedTicket && (
              <Paper
                variant="outlined"
                sx={{
                  p: 2,
                  bgcolor: theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A',
                  borderColor: theme.palette.divider,
                  borderRadius: 3,
                }}
              >
                <Typography variant="subtitle2" fontWeight={700} style={{ color: theme.palette.text.primary, marginBottom: 8 }}>
                  Did this solve your issue?
                </Typography>
                <Box display="flex" gap={1.5} flexWrap="wrap">
                  <Button
                    size="small"
                    variant="contained"
                    color="success"
                    startIcon={<CheckCircleIcon />}
                    onClick={handleResolveClick}
                    style={{ fontWeight: 700, textTransform: 'none' }}
                  >
                    Yes, issue resolved
                  </Button>
                  <Button
                    size="small"
                    variant="contained"
                    style={{ backgroundColor: '#2563EB', fontWeight: 700, textTransform: 'none' }}
                    startIcon={escalating ? <CircularProgress size={14} color="inherit" /> : <ConfirmationNumberIcon />}
                    onClick={handleEscalateClick}
                    disabled={escalating}
                  >
                    {escalating ? 'Routing to Specialist Team...' : 'No, raise support ticket'}
                  </Button>
                </Box>
              </Paper>
            )}

            {feedbackGiven === 'resolved' && (
              <Alert severity="success" sx={{ borderRadius: 2 }}>
                <Typography variant="body2" fontWeight={600}>
                  Wonderful! I'm glad we could resolve that for you. Have a great day!
                </Typography>
              </Alert>
            )}
          </Box>
        )}

        <Typography variant="caption" color="text.secondary" display="block" mt={0.75} textAlign={isUser ? 'right' : 'left'}>
          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Typography>
      </Box>
    </Box>
  )
}

function TypingIndicator() {
  const theme = useTheme()
  return (
    <Box display="flex" alignItems="flex-start" gap={1.5} mb={3}>
      <Avatar
        sx={{
          width: 36, height: 36,
          bgcolor: theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B',
          color: '#2563EB',
          border: `1px solid ${theme.palette.mode === 'light' ? '#BFDBFE' : '#334155'}`,
        }}
      >
        <SmartToyIcon sx={{ fontSize: 20 }} />
      </Avatar>
      <Box
        sx={{
          px: 2.5, py: 1.75,
          bgcolor: theme.palette.mode === 'light' ? '#FFFFFF' : '#1E293B',
          border: `1px solid ${theme.palette.mode === 'light' ? '#E2E8F0' : '#334155'}`,
          borderRadius: '16px 16px 16px 4px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        }}
      >
        <Box display="flex" gap={1} alignItems="center" height={18}>
          <CircularProgress size={14} style={{ color: '#2563EB' }} />
          <Typography variant="caption" color="text.secondary" fontWeight={600}>
            Searching enterprise knowledge...
          </Typography>
        </Box>
      </Box>
    </Box>
  )
}

export default function ChatbotPage() {
  const dispatch = useAppDispatch()
  const theme = useTheme()
  const outletContext = useOutletContext<{ currentRole?: string }>()
  const currentRole = outletContext?.currentRole || 'employee'

  const { messages, loading } = useAppSelector((s) => s.chatbot)
  const [input, setInput] = useState('')
  const [sessionStatus, setSessionStatus] = useState<'Active' | 'Resolved' | 'Ticket Raised' | 'Inactive'>('Active')
  const [sessions, setSessions] = useState<StoredSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string>('')
  const activeSessionIdRef = useRef<string>('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const updateActiveSessionId = (id: string) => {
    activeSessionIdRef.current = id
    setActiveSessionId(id)
  }

  // Load, deduplicate, and filter past sessions from localStorage scoped strictly to currentRole
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const parsed: StoredSession[] = JSON.parse(raw)

        // Deduplicate legacy duplicate sessions (by matching role + user query + message count)
        const seenKeys = new Set<string>()
        const cleaned: StoredSession[] = []
        for (const s of parsed) {
          const firstMsg = s.messages.find((m) => m.role === 'user')?.content || s.title
          const key = `${s.role || 'employee'}_${firstMsg.slice(0, 40)}_${s.messages.length}`
          if (!seenKeys.has(key)) {
            seenKeys.add(key)
            cleaned.push(s)
          }
        }

        if (cleaned.length < parsed.length) {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(cleaned))
        }

        const roleSessions = cleaned.filter((s) => (s.role || 'employee') === currentRole)
        setSessions(roleSessions)
      } else {
        setSessions([])
      }
    } catch (e) {
      console.error('Error loading chat sessions:', e)
    }

    dispatch(clearConversation())
    updateActiveSessionId('')
    setSessionStatus('Active')
  }, [currentRole, dispatch])

  // Auto-save active session thread associated with currentRole
  useEffect(() => {
    if (messages.length === 0) return

    const firstMsg = messages.find((m) => m.role === 'user')?.content || 'Support Chat'
    let autoTitle = firstMsg.slice(0, 32)
    if (firstMsg.includes('sys_db_failover') || firstMsg.includes('secondary node') || firstMsg.includes('mysql')) {
      autoTitle = 'MySQL failover failure'
    } else if (firstMsg.includes('checkout') || firstMsg.includes('500')) {
      autoTitle = 'Payment checkout 500 error'
    }

    const hasTicket = messages.some((m) => m.role === 'assistant' && (m.content.includes('created a Critical incident ticket') || m.content.includes('routed it directly to')))
    const currentStatus = hasTicket ? 'Ticket Raised' : sessionStatus

    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      const allSessions: StoredSession[] = raw ? JSON.parse(raw) : []

      // Use ref synchronously to guarantee 1 conversation = 1 session ID
      let currentId = activeSessionIdRef.current || activeSessionId
      if (!currentId) {
        currentId = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6)
        updateActiveSessionId(currentId)
      }

      // Mark other Active sessions for this role as Inactive so only current session displays as Active
      const updatedAllSessions: StoredSession[] = []
      let foundExisting = false

      for (const s of allSessions) {
        if (s.id === currentId) {
          foundExisting = true
          updatedAllSessions.push({
            id: currentId,
            role: currentRole,
            title: autoTitle,
            timestamp: s.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            status: currentStatus,
            messages: messages,
          })
        } else if ((s.role || 'employee') === currentRole && s.status === 'Active') {
          updatedAllSessions.push({ ...s, status: 'Inactive' })
        } else {
          updatedAllSessions.push(s)
        }
      }

      if (!foundExisting) {
        updatedAllSessions.unshift({
          id: currentId,
          role: currentRole,
          title: autoTitle,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          status: currentStatus,
          messages: messages,
        })
      }

      localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedAllSessions))
      setSessions(updatedAllSessions.filter((s) => (s.role || 'employee') === currentRole))
    } catch (e) {
      console.error('Error saving chat session:', e)
    }
  }, [messages, sessionStatus, currentRole])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = (textToSend?: string) => {
    const text = (textToSend || input).trim()
    if (!text || loading) return
    dispatch(addUserMessage(text))
    dispatch(sendMessage(text))
    setInput('')
  }

  const handleNewChat = () => {
    if (activeSessionIdRef.current) {
      try {
        const raw = localStorage.getItem(STORAGE_KEY)
        if (raw) {
          const allSessions: StoredSession[] = JSON.parse(raw)
          const updated = allSessions.map((s) => {
            if (s.id === activeSessionIdRef.current && s.status === 'Active') {
              return { ...s, status: 'Inactive' as const }
            }
            return s
          })
          localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
          setSessions(updated.filter((s) => (s.role || 'employee') === currentRole))
        }
      } catch (e) {
        console.error('Error setting previous session inactive on new chat:', e)
      }
    }
    dispatch(clearConversation())
    updateActiveSessionId('')
    setSessionStatus('Active')
  }

  const handleSelectSession = (sess: StoredSession) => {
    updateActiveSessionId(sess.id)
    dispatch(setMessages(sess.messages))
    setSessionStatus(sess.status)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const starterChips = [
    'What should I do if the primary database server becomes unavailable?',
    'I forgot my company password. How can I reset it?',
    'My office printer is not printing. What should I do?',
    'How do I configure the company VPN?',
  ]

  const firstUserMsg = messages.find((m) => m.role === 'user')?.content || ''

  const getStatusChip = (st: 'Active' | 'Resolved' | 'Ticket Raised' | 'Inactive', isCurrentlyOpen?: boolean) => {
    if (st === 'Resolved') {
      return <Chip label="Resolved" size="small" style={{ backgroundColor: '#ECFDF5', color: '#059669', fontWeight: 800 }} />
    }
    if (st === 'Ticket Raised') {
      return <Chip label="Ticket Raised" size="small" style={{ backgroundColor: '#F3E8FF', color: '#7C3AED', fontWeight: 800 }} />
    }
    if (isCurrentlyOpen || st === 'Active') {
      return <Chip label="Active" size="small" style={{ backgroundColor: '#EFF6FF', color: '#2563EB', fontWeight: 800 }} />
    }
    return <Chip label="Inactive" size="small" style={{ backgroundColor: '#F1F5F9', color: '#64748B', fontWeight: 700 }} />
  }

  return (
    <Box>
      <PageHeader
        title="SmartDesk ITSM Virtual Agent"
        subtitle={`Enterprise Virtual Support Specialist (${currentRole.toUpperCase()} PORTAL)`}
        action={
          <Box display="flex" alignItems="center" gap={1.5}>
            {getStatusChip(sessionStatus)}
            <Button
              size="small"
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleNewChat}
              style={{ backgroundColor: '#2563EB', fontWeight: 800 }}
            >
              + New Chat
            </Button>
          </Box>
        }
      />

      <Box display="flex" gap={2} height="calc(100vh - 220px)" minHeight={530}>
        {/* Left Role-Scoped History Sidebar */}
        <Paper
          elevation={0}
          sx={{
            width: 250,
            display: { xs: 'none', md: 'flex' },
            flexDirection: 'column',
            bgcolor: 'background.paper',
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: 3,
            p: 2,
          }}
        >
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
            <Box display="flex" alignItems="center" gap={1}>
              <HistoryIcon style={{ color: '#2563EB' }} />
              <Typography variant="subtitle2" fontWeight={800}>
                Chat History
              </Typography>
            </Box>
            <Chip label={sessions.length} size="small" style={{ fontWeight: 700 }} />
          </Box>

          <Button
            fullWidth
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={handleNewChat}
            sx={{ mb: 2, fontWeight: 700, borderRadius: 2 }}
          >
            + New Chat
          </Button>

          <Divider sx={{ mb: 1.5 }} />

          <List sx={{ overflow: 'auto', flexGrow: 1, p: 0 }}>
            {sessions.length === 0 ? (
              <Typography variant="caption" color="text.secondary" textAlign="center" display="block" mt={3}>
                No past {currentRole} sessions saved.
              </Typography>
            ) : (
              sessions.map((s) => {
                const isSelected = s.id === activeSessionId
                return (
                  <ListItemButton
                    key={s.id}
                    selected={isSelected}
                    onClick={() => handleSelectSession(s)}
                    sx={{
                      borderRadius: 2,
                      mb: 0.75,
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      p: 1.25,
                      bgcolor: isSelected ? '#EFF6FF' : 'transparent',
                      border: isSelected ? '1px solid #BFDBFE' : '1px solid transparent',
                    }}
                  >
                    <Box display="flex" alignItems="center" gap={1} width="100%" mb={0.5}>
                      <ChatIcon style={{ fontSize: 16, color: isSelected ? '#2563EB' : theme.palette.text.secondary }} />
                      <Typography variant="body2" fontWeight={700} noWrap sx={{ flexGrow: 1 }}>
                        {s.title}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" alignItems="center" width="100%">
                      <Typography variant="caption" color="text.secondary">
                        {s.timestamp}
                      </Typography>
                      {getStatusChip(s.status, s.id === activeSessionId)}
                    </Box>
                  </ListItemButton>
                )
              })
            )}
          </List>
        </Paper>

        {/* Center Main Chat Panel */}
        <Card sx={{ flex: 1, display: 'flex', flexDirection: 'column', borderRadius: 3 }}>
          <Box flexGrow={1} overflow="auto" p={3}>
            {messages.length === 0 ? (
              <Box
                display="flex"
                flexDirection="column"
                alignItems="center"
                justifyContent="center"
                height="100%"
                gap={2.5}
              >
                <Box
                  sx={{
                    width: 64, height: 64, borderRadius: 4,
                    bgcolor: '#EFF6FF', display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    border: '1px solid #BFDBFE',
                  }}
                >
                  <SmartToyIcon sx={{ color: '#2563EB', fontSize: 36 }} />
                </Box>
                <Box textAlign="center" maxWidth={480}>
                  <Typography variant="h5" fontWeight={800} color="text.primary" mb={1}>
                    SmartDesk Virtual Support Specialist
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Describe your technical issue or ask a question. I can troubleshoot problems step-by-step or automatically route a ticket to specialist teams.
                  </Typography>
                </Box>

                <Box display="flex" flexWrap="wrap" gap={1} justifyContent="center" mt={1} maxWidth={650}>
                  {starterChips.map((s) => (
                    <Chip
                      key={s}
                      label={s}
                      variant="outlined"
                      clickable
                      color="primary"
                      onClick={() => handleSend(s)}
                      sx={{ fontSize: '0.8rem', py: 1.5, px: 0.5, fontWeight: 600 }}
                    />
                  ))}
                </Box>
              </Box>
            ) : (
              <>
                {messages.map((msg, idx) => {
                  const isLastAssistant = msg.role === 'assistant' && (
                    idx === messages.length - 1 ||
                    (idx === messages.length - 2 && messages[messages.length - 1].role === 'user')
                  )
                  return (
                    <MessageBubble
                      key={msg.id}
                      msg={msg}
                      isLastAssistant={isLastAssistant}
                      userInitialPrompt={firstUserMsg}
                      onEscalateSuccess={() => {}}
                      onStatusChange={(status) => setSessionStatus(status)}
                    />
                  )
                })}
                {loading && <TypingIndicator />}
                <div ref={bottomRef} />
              </>
            )}
          </Box>

          <Divider />

          {/* Fixed Input Bar */}
          <Box p={2.5} display="flex" gap={1.5} alignItems="flex-end">
            <TextField
              fullWidth
              multiline
              maxRows={4}
              placeholder="Describe your IT issue or ask a question..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              size="small"
              sx={{ bgcolor: 'background.paper', borderRadius: 2 }}
            />
            <IconButton
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              sx={{
                bgcolor: '#2563EB', color: '#fff', width: 42, height: 42, borderRadius: 2,
                '&:hover': { bgcolor: '#1D4ED8' },
                '&.Mui-disabled': { bgcolor: '#E2E8F0', color: '#94A3B8' },
              }}
            >
              {loading ? <CircularProgress size={18} color="inherit" /> : <SendIcon fontSize="small" />}
            </IconButton>
          </Box>
        </Card>
      </Box>
    </Box>
  )
}
