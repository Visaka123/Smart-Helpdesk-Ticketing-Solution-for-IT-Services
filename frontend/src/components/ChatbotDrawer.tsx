import React, { useState } from 'react'
import { Drawer, Box, Typography, IconButton, TextField, Button, Chip, Paper, CircularProgress, Tooltip } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import SendIcon from '@mui/icons-material/Send'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import ThumbUpIcon from '@mui/icons-material/ThumbUp'
import ThumbDownIcon from '@mui/icons-material/ThumbDown'
import DownloadIcon from '@mui/icons-material/Download'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import DescriptionIcon from '@mui/icons-material/Description'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import LanguageIcon from '@mui/icons-material/Language'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

interface ChatbotDrawerProps {
  open: boolean
  onClose: () => void
  onOpenCreateTicket?: (prefillTitle?: string, prefillDesc?: string) => void
}

interface Message {
  id: number
  sender: 'user' | 'bot'
  text: string
  sources?: any[]
  can_escalate?: boolean
}

export default function ChatbotDrawer({ open, onClose, onOpenCreateTicket }: ChatbotDrawerProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      sender: 'bot',
      text: 'Hello! I am your Copilot AI Assistant. Ask me anything about VPN setup, SAP authorization, database failovers, password resets, or company SOPs.',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')

    setMessages((prev) => [...prev, { id: Date.now(), sender: 'user', text: userMsg }])
    setLoading(true)

    try {
      const res = await axios.post(`${API_BASE}/chatbot/ask`, { message: userMsg })
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'bot',
          text: res.data.answer,
          sources: res.data.sources || [],
          can_escalate: res.data.can_escalate,
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'bot',
          text: 'I am having trouble connecting right now. You can raise a ticket directly for human assistance.',
          can_escalate: true,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleFeedback = async (articleId: number, wasHelpful: boolean) => {
    try {
      await axios.post(`${API_BASE}/chatbot/feedback`, { article_id: articleId, was_helpful: wasHelpful })
      alert(wasHelpful ? 'Thank you for your positive feedback!' : 'Feedback recorded.')
    } catch (e) {
      console.error(e)
    }
  }

  const getDocIcon = (type: string, sourceType?: string) => {
    if (sourceType === 'external_web' || type === 'EXTERNAL_WEB') return <LanguageIcon style={{ color: '#F59E0B', fontSize: 15 }} />
    if (type === 'PDF') return <PictureAsPdfIcon style={{ color: '#EF4444', fontSize: 15 }} />
    if (type === 'DOCX') return <DescriptionIcon style={{ color: '#3B82F6', fontSize: 15 }} />
    if (type === 'RESOLVED_TICKET') return <CheckCircleIcon style={{ color: '#10B981', fontSize: 15 }} />
    return <MenuBookIcon style={{ color: '#F59E0B', fontSize: 15 }} />
  }

  return (
    <Drawer anchor="right" open={open} onClose={onClose} PaperProps={{ sx: { width: { xs: '100%', sm: 450 }, bgcolor: '#0F172A', color: '#FFF' } }}>
      {/* Copilot Virtual Agent Header */}
      <Box p={2} display="flex" justifyContent="space-between" alignItems="center" borderBottom="1px solid #1E293B" bgcolor="#1E293B">
        <Box display="flex" alignItems="center" gap={1.2}>
          <SmartToyIcon style={{ color: '#3B82F6', fontSize: 26 }} />
          <Box>
            <Typography variant="h6" fontWeight={800} style={{ lineHeight: 1.2 }}>
              Copilot AI Virtual Agent
            </Typography>
            <Typography variant="caption" style={{ color: '#94A3B8' }}>
              ServiceNow & Enterprise RAG Search
            </Typography>
          </Box>
        </Box>
        <IconButton onClick={onClose} style={{ color: '#94A3B8' }}>
          <CloseIcon />
        </IconButton>
      </Box>

      {/* Messages Scroll Area */}
      <Box flexGrow={1} p={2} overflow="auto" display="flex" flexDirection="column" gap={2}>
        {messages.map((msg) => (
          <Box key={msg.id} alignSelf={msg.sender === 'user' ? 'flex-end' : 'flex-start'} maxWidth="92%">
            <Paper
              elevation={0}
              sx={{
                p: 2,
                bgcolor: msg.sender === 'user' ? '#2563EB' : '#1E293B',
                color: '#FFF',
                borderRadius: msg.sender === 'user' ? '16px 16px 2px 16px' : '16px 16px 16px 2px',
                border: msg.sender === 'bot' ? '1px solid #334155' : 'none',
              }}
            >
              {msg.sender === 'user' ? (
                <Typography variant="body2" style={{ whiteSpace: 'pre-line', lineHeight: 1.5 }}>
                  {msg.text}
                </Typography>
              ) : (
                <Box sx={{ '& p': { mb: 1, lineHeight: 1.5 }, '& h3': { mt: 1.5, mb: 1, fontSize: '0.95rem', fontWeight: 700 } }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.text ? msg.text.replace(/\\n/g, '\n') : ''}
                  </ReactMarkdown>
                </Box>
              )}

              {/* Source Articles & Citations */}
              {msg.sources && msg.sources.length > 0 && (
                <Box mt={2} pt={1.5} borderTop="1px solid #334155">
                  <Typography variant="caption" style={{ color: '#94A3B8', fontWeight: 700, display: 'block', marginBottom: 8 }}>
                    Sources
                  </Typography>
                  <Box display="flex" flexDirection="column" gap={1.2}>
                    {msg.sources.map((src, idx) => {
                      const isExternalWeb = src.source_type === 'external_web' || src.document_type === 'EXTERNAL_WEB'
                      return (
                        <Paper key={idx} sx={{ p: 1.5, bgcolor: isExternalWeb ? '#451A03' : '#0F172A', border: isExternalWeb ? '1px solid #92400E' : '1px solid #334155', borderRadius: 2 }}>
                          <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
                            <Box display="flex" alignItems="center" gap={0.8}>
                              {getDocIcon(src.document_type, src.source_type)}
                              <Typography variant="caption" fontWeight={700} style={{ color: isExternalWeb ? '#FBBF24' : '#60A5FA' }}>
                                {src.title}
                              </Typography>
                            </Box>
                            <Chip
                              label={isExternalWeb ? `From ${src.domain || 'External Web'}, unverified` : (src.relevance_label || (src.similarity_score && src.similarity_score >= 0.50 ? 'High relevance' : 'Medium relevance'))}
                              size="small"
                              variant="outlined"
                              style={{ fontSize: '0.65rem', height: 18, borderColor: isExternalWeb ? '#F59E0B' : '#334155', color: isExternalWeb ? '#FBBF24' : '#94A3B8', fontWeight: 600 }}
                            />
                          </Box>

                          <Typography variant="caption" style={{ color: '#94A3B8', display: 'block', marginBottom: 8 }}>
                            {src.snippet}
                          </Typography>


                          <Box display="flex" justifyContent="space-between" alignItems="center" pt={0.5} borderTop="1px solid #1E293B">
                            <Chip label={isExternalWeb ? 'EXTERNAL WEB' : (src.document_type || 'PDF')} size="small" style={{ fontSize: '0.62rem', height: 18, backgroundColor: isExternalWeb ? '#78350F' : '#1E293B', color: isExternalWeb ? '#FEF3C7' : '#CBD5E1' }} />

                            <Box display="flex" gap={1} alignItems="center">
                              {src.download_url && (
                                <Button
                                  variant="text"
                                  size="small"
                                  startIcon={isExternalWeb ? <OpenInNewIcon style={{ fontSize: 13 }} /> : <DownloadIcon style={{ fontSize: 13 }} />}
                                  href={src.download_url}
                                  target="_blank"
                                  style={{ color: isExternalWeb ? '#F59E0B' : '#60A5FA', fontSize: '0.7rem', padding: '1px 6px', fontWeight: 700 }}
                                >
                                  {isExternalWeb ? 'Open Link' : 'Download'}
                                </Button>
                              )}

                              <IconButton size="small" style={{ color: '#10B981', padding: 2 }} onClick={() => handleFeedback(src.id, true)}>
                                <ThumbUpIcon style={{ fontSize: 12 }} />
                              </IconButton>
                              <IconButton size="small" style={{ color: '#EF4444', padding: 2 }} onClick={() => handleFeedback(src.id, false)}>
                                <ThumbDownIcon style={{ fontSize: 12 }} />
                              </IconButton>
                            </Box>
                          </Box>
                        </Paper>
                      )
                    })}
                  </Box>
                </Box>
              )}

              {/* Honest Fallback Escalation Button */}
              {msg.can_escalate && onOpenCreateTicket && (
                <Box mt={2}>
                  <Button
                    variant="contained"
                    size="small"
                    style={{ backgroundColor: '#2563EB', fontWeight: 700 }}
                    fullWidth
                    startIcon={<OpenInNewIcon />}
                    onClick={() => {
                      onClose()
                      onOpenCreateTicket('Copilot AI Escalation Ticket', messages[messages.length - 2]?.text || '')
                    }}
                  >
                    Escalate to Human Ticket
                  </Button>
                </Box>
              )}
            </Paper>
          </Box>
        ))}
        {loading && (
          <Box display="flex" alignItems="center" gap={1} p={1}>
            <CircularProgress size={16} style={{ color: '#3B82F6' }} />
            <Typography variant="caption" style={{ color: '#94A3B8' }}>
              Searching Enterprise RAG Knowledge Base...
            </Typography>
          </Box>
        )}
      </Box>

      {/* Input Footer */}
      <Box p={2} borderTop="1px solid #1E293B" bgcolor="#1E293B" display="flex" gap={1}>
        <TextField
          fullWidth
          placeholder="Ask Copilot AI Assistant..."
          size="small"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          sx={{
            '& .MuiOutlinedInput-root': {
              bgcolor: '#0F172A',
              color: '#FFF',
            },
          }}
        />
        <Button variant="contained" style={{ backgroundColor: '#2563EB', minWidth: 44 }} onClick={handleSend}>
          <SendIcon fontSize="small" />
        </Button>
      </Box>
    </Drawer>
  )
}
