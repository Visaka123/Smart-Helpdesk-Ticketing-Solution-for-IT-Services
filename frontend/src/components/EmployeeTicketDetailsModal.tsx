import React, { useState, useEffect } from 'react'
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Box, Typography,
  Button, Chip, Divider, Paper, TextField, CircularProgress, Alert, Rating, IconButton, useTheme
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import SendIcon from '@mui/icons-material/Send'
import ReplayIcon from '@mui/icons-material/Replay'
import StarIcon from '@mui/icons-material/Star'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import DownloadIcon from '@mui/icons-material/Download'
import DescriptionIcon from '@mui/icons-material/Description'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import LockIcon from '@mui/icons-material/Lock'
import axios from 'axios'

import { PriorityBadge, StatusBadge } from './ui/SemanticBadges'

const API_BASE = 'http://localhost:8000'

interface EmployeeTicketDetailsModalProps {
  ticketId: number | null
  open: boolean
  onClose: () => void
  onRefreshList?: () => void
}

export default function EmployeeTicketDetailsModal({
  ticketId,
  open,
  onClose,
  onRefreshList,
}: EmployeeTicketDetailsModalProps) {
  const theme = useTheme()
  const [ticket, setTicket] = useState<any>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Public comment state
  const [newComment, setNewComment] = useState('')
  const [submittingComment, setSubmittingComment] = useState(false)

  // Reopen state
  const [reopenReason, setReopenReason] = useState('')
  const [showReopenBox, setShowReopenBox] = useState(false)
  const [reopening, setReopening] = useState(false)

  // Satisfaction Rating state
  const [rating, setRating] = useState<number | null>(null)
  const [feedbackText, setFeedbackText] = useState('')
  const [submittingRating, setSubmittingRating] = useState(false)
  const [ratingSubmitted, setRatingSubmitted] = useState(false)

  const fetchEmployeeTicket = async () => {
    if (!ticketId) return
    try {
      setLoading(true)
      setError(null)
      const token = localStorage.getItem('token')
      const storedUser = localStorage.getItem('user')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (storedUser) {
        try {
          const u = JSON.parse(storedUser)
          headers['X-User-Id'] = String(u.id)
          headers['X-User-Role'] = u.role || 'employee'
          headers['X-User-Email'] = u.email
          headers['X-User-Name'] = u.name
        } catch (e) {}
      }

      const res = await axios.get(`${API_BASE}/ticket/employee/${ticketId}`, { headers })
      setTicket(res.data)
      if (res.data.satisfaction_rating) {
        setRating(res.data.satisfaction_rating)
        setRatingSubmitted(true)
      }
      if (res.data.satisfaction_feedback) {
        setFeedbackText(res.data.satisfaction_feedback)
      }
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError('Access Denied: You do not have permission to view this ticket.')
      } else {
        setError(err.response?.data?.detail || 'Failed to load ticket details.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open && ticketId) {
      fetchEmployeeTicket()
      setShowReopenBox(false)
      setNewComment('')
    }
  }, [open, ticketId])

  const handleSendComment = async () => {
    if (!newComment.trim() || !ticketId) return
    try {
      setSubmittingComment(true)
      const token = localStorage.getItem('token')
      const storedUser = localStorage.getItem('user')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (storedUser) {
        try {
          const u = JSON.parse(storedUser)
          headers['X-User-Id'] = String(u.id)
          headers['X-User-Role'] = u.role || 'employee'
          headers['X-User-Email'] = u.email
          headers['X-User-Name'] = u.name
        } catch (e) {}
      }

      await axios.post(
        `${API_BASE}/ticket/employee/comment/${ticketId}`,
        { content: newComment },
        { headers }
      )
      setNewComment('')
      await fetchEmployeeTicket()
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to post comment.')
    } finally {
      setSubmittingComment(false)
    }
  }

  const handleReopenTicket = async () => {
    if (!ticketId) return
    try {
      setReopening(true)
      const token = localStorage.getItem('token')
      const storedUser = localStorage.getItem('user')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (storedUser) {
        try {
          const u = JSON.parse(storedUser)
          headers['X-User-Id'] = String(u.id)
          headers['X-User-Role'] = u.role || 'employee'
          headers['X-User-Email'] = u.email
          headers['X-User-Name'] = u.name
        } catch (e) {}
      }

      await axios.post(
        `${API_BASE}/ticket/employee/reopen/${ticketId}`,
        { reason: reopenReason },
        { headers }
      )
      setShowReopenBox(false)
      setReopenReason('')
      await fetchEmployeeTicket()
      if (onRefreshList) onRefreshList()
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to reopen ticket.')
    } finally {
      setReopening(false)
    }
  }

  const handleSubmitRating = async (newValue: number | null) => {
    if (!newValue || !ticketId) return
    setRating(newValue)
    try {
      setSubmittingRating(true)
      const token = localStorage.getItem('token')
      const storedUser = localStorage.getItem('user')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (storedUser) {
        try {
          const u = JSON.parse(storedUser)
          headers['X-User-Id'] = String(u.id)
          headers['X-User-Role'] = u.role || 'employee'
          headers['X-User-Email'] = u.email
          headers['X-User-Name'] = u.name
        } catch (e) {}
      }

      await axios.post(
        `${API_BASE}/ticket/employee/rate/${ticketId}`,
        { rating: newValue, feedback: feedbackText },
        { headers }
      )
      setRatingSubmitted(true)
    } catch (e: any) {
      console.error('Failed to submit rating:', e)
    } finally {
      setSubmittingRating(false)
    }
  }

  const isResolvedOrClosed = ticket && (ticket.status === 'resolved' || ticket.status === 'closed')

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth PaperProps={{ sx: { borderRadius: 3, p: 1 } }}>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1 }}>
        <Box display="flex" alignItems="center" gap={1.5}>
          <Typography variant="h6" fontWeight={800} style={{ color: '#2563EB' }}>
            Ticket #{ticketId}
          </Typography>
          {ticket && <StatusBadge status={ticket.status} />}
          {ticket && <PriorityBadge priority={ticket.priority} />}
        </Box>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ py: 2.5 }}>
        {loading ? (
          <Box display="flex" justifyContent="center" py={6}>
            <CircularProgress size={28} style={{ color: '#2563EB' }} />
          </Box>
        ) : error ? (
          <Alert severity="error" icon={<LockIcon />} sx={{ borderRadius: 2 }}>
            <Typography variant="subtitle2" fontWeight={700}>
              {error}
            </Typography>
            <Typography variant="caption">
              Employees can only access their own support requests.
            </Typography>
          </Alert>
        ) : ticket ? (
          <Box display="flex" flexDirection="column" gap={3}>
            {/* Subject & Metadata Header */}
            <Box>
              <Typography variant="h5" fontWeight={800} style={{ color: theme.palette.text.primary, marginBottom: 6 }}>
                {ticket.title}
              </Typography>
              <Box display="flex" gap={2} alignItems="center" flexWrap="wrap">
                <Chip label={`Category: ${ticket.category || 'General IT'}`} size="small" style={{ backgroundColor: theme.palette.mode === 'dark' ? '#1E293B' : '#F1F5F9', fontWeight: 600 }} />
                <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                  Created: {ticket.created_at ? new Date(ticket.created_at).toLocaleString() : '—'}
                </Typography>
                {ticket.resolved_at && (
                  <Typography variant="caption" style={{ color: '#10B981', fontWeight: 700 }}>
                    Resolved: {new Date(ticket.resolved_at).toLocaleString()}
                  </Typography>
                )}
              </Box>
            </Box>

            {/* Description Box */}
            <Paper elevation={0} sx={{ p: 2, bgcolor: theme.palette.mode === 'dark' ? '#0F172A' : '#F8FAFC', border: `1px solid ${theme.palette.divider}`, borderRadius: 2 }}>
              <Typography variant="caption" fontWeight={700} style={{ color: theme.palette.text.secondary, display: 'block', mb: 0.5 }}>
                DESCRIPTION
              </Typography>
              <Typography variant="body2" style={{ whiteSpace: 'pre-line', lineHeight: 1.6 }}>
                {ticket.description}
              </Typography>
            </Paper>

            {/* User-Facing Resolution Summary Box (If Resolved) */}
            {ticket.resolution_summary && (
              <Paper elevation={0} sx={{ p: 2.5, bgcolor: theme.palette.mode === 'dark' ? '#064E3B' : '#ECFDF5', border: '1px solid #10B981', borderRadius: 2 }}>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <CheckCircleIcon style={{ color: '#10B981' }} />
                  <Typography variant="subtitle2" fontWeight={800} style={{ color: theme.palette.mode === 'dark' ? '#34D399' : '#065F46' }}>
                    Official Solution & Resolution Summary
                  </Typography>
                </Box>
                <Typography variant="body2" style={{ color: theme.palette.mode === 'dark' ? '#D1FAE5' : '#047857', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
                  {ticket.resolution_summary}
                </Typography>
              </Paper>
            )}

            {/* Satisfaction Rating Section for Resolved Tickets */}
            {isResolvedOrClosed && (
              <Paper elevation={0} sx={{ p: 2, bgcolor: theme.palette.mode === 'dark' ? '#1E293B' : '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 2 }}>
                <Typography variant="subtitle2" fontWeight={700} style={{ color: '#1E40AF', mb: 1 }}>
                  How satisfied were you with this resolution?
                </Typography>
                <Box display="flex" alignItems="center" gap={2} mb={1}>
                  <Rating
                    value={rating}
                    onChange={(_, newValue) => handleSubmitRating(newValue)}
                    disabled={submittingRating}
                    emptyIcon={<StarIcon style={{ opacity: 0.4 }} fontSize="inherit" />}
                  />
                  {ratingSubmitted && (
                    <Typography variant="caption" style={{ color: '#10B981', fontWeight: 700 }}>
                      Thank you for your rating!
                    </Typography>
                  )}
                </Box>
              </Paper>
            )}

            {/* Public Conversation Timeline */}
            <Box>
              <Typography variant="subtitle2" fontWeight={800} mb={1.5}>
                Public Conversation & Ticket Activity ({ticket.comments?.length || 0})
              </Typography>
              <Box display="flex" flexDirection="column" gap={1.5}>
                {ticket.comments && ticket.comments.length > 0 ? (
                  ticket.comments.map((c: any) => (
                    <Paper
                      key={c.id}
                      elevation={0}
                      sx={{
                        p: 2,
                        bgcolor: c.author_role === 'employee' ? (theme.palette.mode === 'dark' ? '#1E293B' : '#F1F5F9') : (theme.palette.mode === 'dark' ? '#1E3A8A' : '#EFF6FF'),
                        border: `1px solid ${c.author_role === 'employee' ? theme.palette.divider : '#BFDBFE'}`,
                        borderRadius: 2,
                      }}
                    >
                      <Box display="flex" justifyContent="space-between" mb={0.5}>
                        <Typography variant="caption" fontWeight={700} style={{ color: c.author_role === 'employee' ? theme.palette.text.primary : '#2563EB' }}>
                          {c.author_name} ({c.author_role === 'employee' ? 'You' : 'Support Specialist'})
                        </Typography>
                        <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                          {c.created_at ? new Date(c.created_at).toLocaleString() : '—'}
                        </Typography>
                      </Box>
                      <Typography variant="body2" style={{ whiteSpace: 'pre-line', lineHeight: 1.5 }}>
                        {c.content}
                      </Typography>
                    </Paper>
                  ))
                ) : (
                  <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontStyle: 'italic' }}>
                    No comments posted yet. Use the message box below to reply.
                  </Typography>
                )}
              </Box>
            </Box>

            {/* Public Comment Input */}
            <Box display="flex" gap={1}>
              <TextField
                fullWidth
                placeholder="Type your message to support..."
                size="small"
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSendComment()}
                disabled={submittingComment}
              />
              <Button
                variant="contained"
                style={{ backgroundColor: '#2563EB', fontWeight: 700 }}
                onClick={handleSendComment}
                disabled={submittingComment || !newComment.trim()}
                startIcon={<SendIcon fontSize="small" />}
              >
                Send
              </Button>
            </Box>

            {/* Related KB Articles & SOP Guides */}
            {ticket.suggested_kb_articles && ticket.suggested_kb_articles.length > 0 && (
              <Box pt={1}>
                <Typography variant="caption" fontWeight={800} style={{ color: theme.palette.text.secondary, display: 'block', mb: 1 }}>
                  RECOMMENDED HELPDESK GUIDES & DOWNLOADS:
                </Typography>
                <Box display="flex" flexDirection="column" gap={1}>
                  {ticket.suggested_kb_articles.map((kb: any, idx: number) => (
                    <Paper key={idx} sx={{ p: 1.5, bgcolor: theme.palette.mode === 'dark' ? '#0F172A' : '#F8FAFC', border: `1px solid ${theme.palette.divider}`, borderRadius: 2 }}>
                      <Box display="flex" justifyContent="space-between" alignItems="center">
                        <Box display="flex" alignItems="center" gap={1}>
                          {kb.document_type === 'PDF' ? <PictureAsPdfIcon style={{ color: '#EF4444', fontSize: 18 }} /> : <DescriptionIcon style={{ color: '#2563EB', fontSize: 18 }} />}
                          <Typography variant="caption" fontWeight={700} style={{ color: '#2563EB' }}>
                            {kb.title}
                          </Typography>
                        </Box>
                        {kb.download_url && (
                          <Button
                            variant="text"
                            size="small"
                            startIcon={<DownloadIcon style={{ fontSize: 14 }} />}
                            href={kb.download_url}
                            target="_blank"
                            style={{ color: '#2563EB', fontSize: '0.75rem', fontWeight: 700 }}
                          >
                            Download
                          </Button>
                        )}
                      </Box>
                    </Paper>
                  ))}
                </Box>
              </Box>
            )}

            {/* Reopen Ticket Box */}
            {isResolvedOrClosed && (
              <Box pt={1} borderTop={`1px solid ${theme.palette.divider}`}>
                {!showReopenBox ? (
                  <Button
                    variant="outlined"
                    color="warning"
                    size="small"
                    startIcon={<ReplayIcon />}
                    onClick={() => setShowReopenBox(true)}
                  >
                    Need More Help? Reopen Ticket
                  </Button>
                ) : (
                  <Paper elevation={0} sx={{ p: 2, bgcolor: theme.palette.mode === 'dark' ? '#1E293B' : '#FFFBEB', border: '1px solid #F59E0B', borderRadius: 2 }}>
                    <Typography variant="subtitle2" fontWeight={700} style={{ color: '#D97706', mb: 1 }}>
                      Reopen Support Ticket
                    </Typography>
                    <TextField
                      fullWidth
                      multiline
                      rows={2}
                      size="small"
                      placeholder="Explain why the issue is not resolved..."
                      value={reopenReason}
                      onChange={(e) => setReopenReason(e.target.value)}
                      sx={{ mb: 1.5 }}
                    />
                    <Box display="flex" gap={1}>
                      <Button
                        variant="contained"
                        color="warning"
                        size="small"
                        onClick={handleReopenTicket}
                        disabled={reopening}
                      >
                        Confirm Reopen
                      </Button>
                      <Button variant="text" size="small" onClick={() => setShowReopenBox(false)}>
                        Cancel
                      </Button>
                    </Box>
                  </Paper>
                )}
              </Box>
            )}
          </Box>
        ) : null}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} variant="outlined" size="small">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  )
}
