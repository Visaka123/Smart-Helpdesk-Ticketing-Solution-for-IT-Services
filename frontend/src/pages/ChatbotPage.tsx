import { useState, useRef, useEffect } from 'react'
import {
  Box, Card, CardContent, Typography, TextField, IconButton,
  CircularProgress, Divider, Button, Chip, Paper, Avatar,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import PersonIcon from '@mui/icons-material/Person'
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined'
import { useAppDispatch, useAppSelector } from '../hooks/redux'
import { sendMessage, addUserMessage, clearConversation } from '../store/slices/chatSlice'
import PageHeader from '../components/ui/PageHeader'
import type { ChatMessage } from '../types'

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  return (
    <Box
      display="flex"
      flexDirection={isUser ? 'row-reverse' : 'row'}
      alignItems="flex-start"
      gap={1.5}
      mb={2.5}
    >
      <Avatar
        sx={{
          width: 32, height: 32, flexShrink: 0,
          bgcolor: isUser ? '#1E3A8A' : '#F1F5F9',
          color: isUser ? '#fff' : '#475569',
        }}
      >
        {isUser ? <PersonIcon sx={{ fontSize: 16 }} /> : <SmartToyIcon sx={{ fontSize: 16 }} />}
      </Avatar>

      <Box maxWidth="75%">
        <Box
          sx={{
            px: 2, py: 1.5,
            bgcolor: isUser ? '#1E3A8A' : '#F8FAFC',
            color: isUser ? '#fff' : 'text.primary',
            borderRadius: isUser ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
            border: isUser ? 'none' : '1px solid #E2E8F0',
          }}
        >
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
            {msg.content}
          </Typography>
        </Box>

        {!isUser && msg.confidence !== undefined && (
          <Box display="flex" alignItems="center" gap={1} mt={1}>
            <Typography variant="caption" color="text.secondary">Confidence:</Typography>
            <Chip
              label={`${Math.round((msg.confidence || 0) * 100)}%`}
              size="small"
              color={msg.confidence > 0.7 ? 'success' : msg.confidence > 0.4 ? 'warning' : 'default'}
              variant="outlined"
            />
          </Box>
        )}

        {!isUser && msg.suggested_actions && msg.suggested_actions.length > 0 && (
          <Box mt={1.5}>
            <Box display="flex" alignItems="center" gap={0.5} mb={0.75}>
              <LightbulbOutlinedIcon sx={{ fontSize: 13, color: '#D97706' }} />
              <Typography variant="caption" color="text.secondary" fontWeight={600}>
                Suggested Actions
              </Typography>
            </Box>
            <Box display="flex" flexWrap="wrap" gap={0.75}>
              {msg.suggested_actions.map((action, i) => (
                <Chip key={i} label={action} size="small" variant="outlined" sx={{ fontSize: '0.7rem' }} />
              ))}
            </Box>
          </Box>
        )}

        {!isUser && msg.similar_tickets && msg.similar_tickets.length > 0 && (
          <Box mt={1.5}>
            <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.75}>
              Related Tickets
            </Typography>
            {msg.similar_tickets.slice(0, 3).map((t) => (
              <Paper
                key={t.id}
                variant="outlined"
                sx={{ p: 1, mb: 0.5, bgcolor: '#F8FAFC', borderColor: '#E2E8F0' }}
              >
                <Typography variant="caption" fontWeight={500} display="block">{t.title}</Typography>
                <Typography variant="caption" color="text.secondary">{t.status} — {t.predicted_team || 'Unassigned'}</Typography>
              </Paper>
            ))}
          </Box>
        )}

        <Typography variant="caption" color="text.secondary" display="block" mt={0.5}
          textAlign={isUser ? 'right' : 'left'}>
          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Typography>
      </Box>
    </Box>
  )
}

function TypingIndicator() {
  return (
    <Box display="flex" alignItems="flex-start" gap={1.5} mb={2}>
      <Avatar sx={{ width: 32, height: 32, bgcolor: '#F1F5F9', color: '#475569' }}>
        <SmartToyIcon sx={{ fontSize: 16 }} />
      </Avatar>
      <Box sx={{ px: 2, py: 1.5, bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '12px 12px 12px 2px' }}>
        <Box display="flex" gap={0.5} alignItems="center" height={16}>
          {[0, 1, 2].map((i) => (
            <Box
              key={i}
              sx={{
                width: 6, height: 6, borderRadius: '50%', bgcolor: '#94A3B8',
                animation: 'bounce 1.2s infinite',
                animationDelay: `${i * 0.2}s`,
                '@keyframes bounce': {
                  '0%, 80%, 100%': { transform: 'scale(0.8)', opacity: 0.5 },
                  '40%': { transform: 'scale(1.2)', opacity: 1 },
                },
              }}
            />
          ))}
        </Box>
      </Box>
    </Box>
  )
}

export default function ChatbotPage() {
  const dispatch = useAppDispatch()
  const { messages, loading } = useAppSelector((s) => s.chatbot)
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = () => {
    const text = input.trim()
    if (!text || loading) return
    dispatch(addUserMessage(text))
    dispatch(sendMessage(text))
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const suggestions = [
    'My VPN is not connecting',
    'I forgot my password',
    'How do I install software?',
    'My email is not working',
    'My laptop is running slow',
  ]

  return (
    <Box>
      <PageHeader
        title="IT Support Assistant"
        subtitle="Get instant help for common IT issues before raising a ticket"
        action={
          messages.length > 0 ? (
            <Button
              size="small"
              variant="outlined"
              startIcon={<DeleteOutlineIcon />}
              onClick={() => dispatch(clearConversation())}
            >
              Clear
            </Button>
          ) : undefined
        }
      />

      <Box display="flex" gap={2} height="calc(100vh - 220px)" minHeight={500}>
        <Card sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {/* Chat history */}
          <Box flexGrow={1} overflow="auto" p={2.5}>
            {messages.length === 0 ? (
              <Box
                display="flex"
                flexDirection="column"
                alignItems="center"
                justifyContent="center"
                height="100%"
                gap={2}
              >
                <Box
                  sx={{
                    width: 56, height: 56, borderRadius: 3,
                    bgcolor: '#EFF6FF', display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  <SmartToyIcon sx={{ color: '#2563EB', fontSize: 28 }} />
                </Box>
                <Box textAlign="center">
                  <Typography variant="h5" color="text.primary" mb={0.5}>
                    IT Support Assistant
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Describe your issue and I will try to help you resolve it
                  </Typography>
                </Box>
                <Box display="flex" flexWrap="wrap" gap={1} justifyContent="center" mt={1}>
                  {suggestions.map((s) => (
                    <Chip
                      key={s}
                      label={s}
                      variant="outlined"
                      clickable
                      size="small"
                      onClick={() => setInput(s)}
                      sx={{ fontSize: '0.75rem' }}
                    />
                  ))}
                </Box>
              </Box>
            ) : (
              <>
                {messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)}
                {loading && <TypingIndicator />}
                <div ref={bottomRef} />
              </>
            )}
          </Box>

          <Divider />

          {/* Input area */}
          <Box p={2} display="flex" gap={1.5} alignItems="flex-end">
            <TextField
              fullWidth
              multiline
              maxRows={4}
              placeholder="Describe your IT issue here, e.g. My VPN is not connecting..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              size="small"
            />
            <IconButton
              onClick={handleSend}
              disabled={!input.trim() || loading}
              sx={{
                bgcolor: '#1E3A8A', color: '#fff', width: 38, height: 38,
                '&:hover': { bgcolor: '#2563EB' },
                '&.Mui-disabled': { bgcolor: '#E2E8F0', color: '#94A3B8' },
              }}
            >
              {loading ? <CircularProgress size={16} color="inherit" /> : <SendIcon fontSize="small" />}
            </IconButton>
          </Box>
        </Card>

        {/* Side info panel */}
        <Box width={260} display={{ xs: 'none', lg: 'flex' }} flexDirection="column" gap={2}>
          <Card>
            <CardContent sx={{ p: 2 }}>
              <Typography variant="h6" mb={1.5}>Capabilities</Typography>
              {[
                'Fix VPN and remote access issues',
                'Step-by-step troubleshooting guides',
                'Password and account help',
                'Find similar resolved issues',
                'Know when to escalate to IT team',
              ].map((item) => (
                <Box key={item} display="flex" gap={1} mb={1} alignItems="flex-start">
                  <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: '#2563EB', mt: 0.75, flexShrink: 0 }} />
                  <Typography variant="body2" color="text.secondary">{item}</Typography>
                </Box>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardContent sx={{ p: 2 }}>
              <Typography variant="h6" mb={1.5}>Session Info</Typography>
              <Box display="flex" justifyContent="space-between" mb={1}>
                <Typography variant="body2" color="text.secondary">Messages</Typography>
                <Typography variant="body2" fontWeight={600}>{messages.length}</Typography>
              </Box>
              <Box display="flex" justifyContent="space-between">
                <Typography variant="body2" color="text.secondary">AI Responses</Typography>
                <Typography variant="body2" fontWeight={600}>
                  {messages.filter((m) => m.role === 'assistant').length}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  )
}
