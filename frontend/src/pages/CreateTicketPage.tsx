import React, { useState } from 'react'
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Grid,
  Chip,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  Divider,
  useTheme,
  Stack,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import CancelIcon from '@mui/icons-material/Cancel'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import LockIcon from '@mui/icons-material/Lock'
import GroupIcon from '@mui/icons-material/Group'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

export default function CreateTicketPage() {
  const navigate = useNavigate()
  const theme = useTheme()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [department, setDepartment] = useState('Finance')
  const [requesterName, setRequesterName] = useState('Alice Employee')
  const [submitting, setSubmitting] = useState(false)

  // Interstitial Modal State
  const [interstitialOpen, setInterstitialOpen] = useState(false)
  const [interstitialMatch, setInterstitialMatch] = useState<any>(null)
  const [interstitialType, setInterstitialType] = useState<'open' | 'resolved' | null>(null)

  // Hard Block Modal State
  const [blockDialogOpen, setBlockDialogOpen] = useState(false)
  const [blockData, setBlockData] = useState<any>(null)

  // Ticket Created Confirmation Modal
  const [successDialogOpen, setSuccessDialogOpen] = useState(false)
  const [createdTicket, setCreatedTicket] = useState<any>(null)

  const executeCreateTicket = async (forceSkipCheck = false) => {
    setSubmitting(true)
    try {
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

      const res = await axios.post(`${API_BASE}/ticket/create`, {
        title,
        description,
        requester_name: requesterName,
        requester_department: department,
        skip_duplicate_check: forceSkipCheck,
      }, { headers })

      if (res.data.is_hard_blocked) {
        setBlockData(res.data)
        setBlockDialogOpen(true)
        setSubmitting(false)
        return
      }

      setCreatedTicket(res.data.ticket || res.data)
      setSuccessDialogOpen(true)
    } catch (err) {
      console.error('Error submitting ticket:', err)
      alert('Failed to submit ticket. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !description.trim()) {
      alert('Please enter both ticket title and description.')
      return
    }

    setSubmitting(true)
    try {
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

      // 1. Run Pre-Submission Duplicate Check using backend RAG similarity matcher
      const dupRes = await axios.post(`${API_BASE}/ticket/check-duplicate`, {
        title,
        description,
      }, { headers })

      const data = dupRes.data
      if (data && data.has_duplicate && data.top_match) {
        const match = data.top_match
        if (data.has_resolved_match && (match.status === 'resolved' || match.status === 'closed')) {
          setInterstitialMatch(match)
          setInterstitialType('resolved')
          setInterstitialOpen(true)
          setSubmitting(false)
          return
        } else if (data.has_open_match) {
          setInterstitialMatch(match)
          setInterstitialType('open')
          setInterstitialOpen(true)
          setSubmitting(false)
          return
        }
      }

      // No match above threshold -> submit immediately
      await executeCreateTicket(false)
    } catch (err) {
      console.error('Error checking duplicate ticket:', err)
      await executeCreateTicket(false)
    }
  }

  return (
    <Box maxWidth={720} mx="auto" py={3}>
      <Paper
        elevation={0}
        sx={{
          p: 4,
          bgcolor: 'background.paper',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 3,
          boxShadow: theme.palette.mode === 'light' ? '0 4px 20px rgba(0, 0, 0, 0.05)' : 'none',
        }}
      >
        <Box mb={3.5}>
          <Typography variant="h4" fontWeight={800} color="text.primary" gutterBottom>
            Create Support Ticket
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Submit an IT service request or report an issue. Your ticket will be automatically classified and routed to the appropriate support team.
          </Typography>
        </Box>

        <form onSubmit={handleSubmit}>
          <Stack spacing={3}>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField
                  label="Requester Name"
                  fullWidth
                  required
                  value={requesterName}
                  onChange={(e) => setRequesterName(e.target.value)}
                  placeholder="e.g. Alice Employee"
                  variant="outlined"
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  select
                  label="Department"
                  fullWidth
                  required
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  SelectProps={{ native: true }}
                  variant="outlined"
                >
                  <option value="Finance">Finance</option>
                  <option value="Sales">Sales</option>
                  <option value="Engineering">Engineering</option>
                  <option value="Human Resources">Human Resources</option>
                </TextField>
              </Grid>
            </Grid>

            <TextField
              label="Ticket Title"
              fullWidth
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Unable to access financial reporting portal"
              variant="outlined"
            />

            <TextField
              label="Detailed Description"
              fullWidth
              required
              multiline
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Please provide details about the issue, including error messages, steps to reproduce, or impacted systems..."
              variant="outlined"
            />

            <Divider sx={{ my: 1 }} />

            <Box display="flex" justifyContent="flex-end" gap={2}>
              <Button
                variant="outlined"
                color="inherit"
                onClick={() => navigate('/tickets')}
                startIcon={<CancelIcon />}
                disabled={submitting}
                sx={{ px: 3, py: 1, fontWeight: 700 }}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="contained"
                disabled={submitting}
                startIcon={<SendIcon />}
                sx={{
                  px: 4,
                  py: 1,
                  fontWeight: 700,
                  bgcolor: '#2563EB',
                  '&:hover': { bgcolor: '#1D4ED8' },
                }}
              >
                {submitting ? 'Submitting...' : 'Submit Ticket'}
              </Button>
            </Box>
          </Stack>
        </form>
      </Paper>

      {/* COMPACT PROFESSIONAL CREATION SUCCESS DIALOG */}
      {createdTicket && (
        <Dialog
          open={successDialogOpen}
          onClose={() => setSuccessDialogOpen(false)}
          maxWidth="xs"
          fullWidth
          PaperProps={{
            sx: { borderRadius: 3, p: 1 },
          }}
        >
          <DialogTitle sx={{ pb: 1, display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <CheckCircleOutlineIcon sx={{ color: '#10B981', fontSize: 32 }} />
            <Box>
              <Typography variant="h6" fontWeight={800} color="text.primary">
                Ticket Created Successfully
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Ticket ID: #{createdTicket.id}
              </Typography>
            </Box>
          </DialogTitle>

          <DialogContent sx={{ py: 2 }}>
            <Paper
              variant="outlined"
              sx={{ p: 2.5, bgcolor: theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A', borderRadius: 2 }}
            >
              <Stack spacing={1.8}>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" color="text.secondary" fontWeight={600}>
                    Category
                  </Typography>
                  <Typography variant="body2" fontWeight={800} color="primary.main">
                    {createdTicket.category || createdTicket.predicted_category || 'Hardware'}
                  </Typography>
                </Box>

                <Divider light />

                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" color="text.secondary" fontWeight={600}>
                    Assigned Team
                  </Typography>
                  <Typography variant="body2" fontWeight={800} color="text.primary">
                    {createdTicket.assigned_team || createdTicket.predicted_team || 'General Support'}
                  </Typography>
                </Box>

                <Divider light />

                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" color="text.secondary" fontWeight={600}>
                    Priority
                  </Typography>
                  <Chip
                    label={createdTicket.priority || 'Medium'}
                    size="small"
                    color={
                      createdTicket.priority === 'Critical'
                        ? 'error'
                        : createdTicket.priority === 'High'
                        ? 'warning'
                        : 'primary'
                    }
                    sx={{ fontWeight: 800, height: 24 }}
                  />
                </Box>

                <Divider light />

                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" color="text.secondary" fontWeight={600}>
                    SLA Target
                  </Typography>
                  <Box display="flex" alignItems="center" gap={0.5}>
                    <AccessTimeIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                    <Typography variant="body2" fontWeight={800} color="text.primary">
                      {createdTicket.sla_hours ? `${createdTicket.sla_hours} hours` : '24 hours'}
                    </Typography>
                  </Box>
                </Box>
              </Stack>
            </Paper>
          </DialogContent>

          <DialogActions sx={{ p: 2, pt: 1 }}>
            <Button
              variant="contained"
              fullWidth
              onClick={() => {
                setSuccessDialogOpen(false)
                navigate('/dashboard')
              }}
              sx={{ bgcolor: '#2563EB', fontWeight: 700, py: 1 }}
            >
              Return to Dashboard
            </Button>
          </DialogActions>
        </Dialog>
      )}

      {/* PRE-SUBMISSION SIMILARITY INTERSTITIAL DIALOG */}
      {interstitialMatch && (
        <Dialog
          open={interstitialOpen}
          onClose={() => setInterstitialOpen(false)}
          maxWidth="sm"
          fullWidth
          PaperProps={{ sx: { borderRadius: 3 } }}
        >
          <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5, pb: 1 }}>
            {interstitialType === 'resolved' ? (
              <CheckCircleOutlineIcon sx={{ color: '#059669', fontSize: 28 }} />
            ) : (
              <GroupIcon sx={{ color: '#D97706', fontSize: 28 }} />
            )}
            <Box>
              <Typography variant="h6" fontWeight={800} color="text.primary">
                {interstitialType === 'resolved'
                  ? 'Similar Resolved Issue Found'
                  : 'Similar Open Incident In Progress'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Matched against existing Ticket #{interstitialMatch.ticket_id} (Relevance:{' '}
                {Math.round((interstitialMatch.semantic_score || 0.85) * 100)}%)
              </Typography>
            </Box>
          </DialogTitle>

          <DialogContent sx={{ py: 2 }}>
            {interstitialType === 'resolved' ? (
              <Paper
                variant="outlined"
                sx={{
                  p: 2.5,
                  bgcolor: theme.palette.mode === 'light' ? '#ECFDF5' : '#064E3B',
                  borderColor: '#A7F3D0',
                  borderRadius: 2.5,
                }}
              >
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <CheckCircleOutlineIcon sx={{ color: '#059669', fontSize: 20 }} />
                  <Typography variant="subtitle2" fontWeight={800} sx={{ color: '#065F46' }}>
                    Official Verified Solution — Ticket #{interstitialMatch.ticket_id}
                  </Typography>
                </Box>
                <Typography variant="body2" fontWeight={700} sx={{ color: '#047857', mb: 1 }}>
                  {interstitialMatch.title}
                </Typography>
                <Divider sx={{ my: 1.5, borderColor: '#A7F3D0' }} />
                <Typography variant="caption" fontWeight={800} sx={{ color: '#065F46', display: 'block', mb: 0.5 }}>
                  RECOMMENDED RESOLUTION SUMMARY:
                </Typography>
                <Typography variant="body2" sx={{ color: '#064E3B', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
                  {interstitialMatch.resolution_summary || 'Verified fix applied by operations.'}
                </Typography>
                {interstitialMatch.resolution_detail && (
                  <Typography variant="caption" sx={{ color: '#047857', display: 'block', mt: 1, fontStyle: 'italic' }}>
                    {interstitialMatch.resolution_detail}
                  </Typography>
                )}
              </Paper>
            ) : (
              <Paper
                variant="outlined"
                sx={{
                  p: 2.5,
                  bgcolor: theme.palette.mode === 'light' ? '#FFFBEB' : '#451A03',
                  borderColor: '#FDE68A',
                  borderRadius: 2.5,
                }}
              >
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <GroupIcon sx={{ color: '#D97706', fontSize: 20 }} />
                  <Typography variant="subtitle2" fontWeight={800} sx={{ color: '#92400E' }}>
                    Active Incident Already In Progress — Ticket #{interstitialMatch.ticket_id}
                  </Typography>
                </Box>
                <Typography variant="body2" fontWeight={700} sx={{ color: '#B45309', mb: 1 }}>
                  {interstitialMatch.title}
                </Typography>
                <Box display="flex" gap={1} my={1.5}>
                  <Chip
                    label={`Status: ${String(interstitialMatch.status).toUpperCase()}`}
                    size="small"
                    style={{ backgroundColor: '#FEF3C7', color: '#B45309', fontWeight: 800 }}
                  />
                  <Chip
                    label={`Team: ${interstitialMatch.assigned_team || 'IT Support'}`}
                    size="small"
                    style={{ backgroundColor: '#EFF6FF', color: '#2563EB', fontWeight: 800 }}
                  />
                </Box>
                <Typography variant="caption" color="text.secondary" display="block">
                  {interstitialMatch.description}
                </Typography>
                {!interstitialMatch.is_own_ticket && (
                  <Alert severity="info" icon={false} sx={{ mt: 1.5, py: 0.5, px: 1.5, fontSize: '0.78rem', borderRadius: 1.5 }}>
                    This incident was reported by another employee. Support is actively resolving it org-wide.
                  </Alert>
                )}
              </Paper>
            )}
          </DialogContent>

          <DialogActions sx={{ p: 2.5, pt: 1, gap: 1.5, flexWrap: 'wrap' }}>
            {interstitialType === 'resolved' ? (
              <>
                <Button
                  variant="contained"
                  color="success"
                  fullWidth
                  onClick={() => {
                    setInterstitialOpen(false)
                    navigate('/dashboard')
                  }}
                  sx={{ fontWeight: 800, py: 1.25 }}
                >
                  This solves my issue
                </Button>
                <Button
                  variant="outlined"
                  color="inherit"
                  fullWidth
                  onClick={() => {
                    setInterstitialOpen(false)
                    executeCreateTicket(true)
                  }}
                  sx={{ fontWeight: 700, textTransform: 'none' }}
                >
                  Still create a ticket
                </Button>
              </>
            ) : (
              <>
                {interstitialMatch.is_own_ticket ? (
                  <Button
                    variant="contained"
                    fullWidth
                    onClick={() => {
                      const ticketId = interstitialMatch?.ticket_id || interstitialMatch?.id
                      setInterstitialOpen(false)
                      if (ticketId) {
                        navigate(`/tickets?open=${ticketId}`, { state: { openTicketId: ticketId } })
                      } else {
                        navigate('/tickets')
                      }
                    }}
                    sx={{ bgcolor: '#2563EB', fontWeight: 800, py: 1.25 }}
                  >
                    View my existing ticket
                  </Button>
                ) : (
                  <Button
                    variant="contained"
                    fullWidth
                    onClick={() => {
                      setInterstitialOpen(false)
                    }}
                    sx={{ bgcolor: '#2563EB', fontWeight: 800, py: 1.25 }}
                  >
                    Got it, already tracked
                  </Button>
                )}
                <Button
                  variant="outlined"
                  color="inherit"
                  fullWidth
                  onClick={() => {
                    setInterstitialOpen(false)
                    executeCreateTicket(true)
                  }}
                  sx={{ fontWeight: 700, textTransform: 'none' }}
                >
                  This is different, create anyway
                </Button>
              </>
            )}
          </DialogActions>
        </Dialog>
      )}

      {/* HARD BLOCK DUPLICATE MODAL */}
      {blockData && (
        <Dialog open={blockDialogOpen} onClose={() => setBlockDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, color: blockData.block_type === 'open_ticket_linked' ? '#D97706' : '#10B981' }}>
            <LockIcon sx={{ color: blockData.block_type === 'open_ticket_linked' ? '#D97706' : '#10B981' }} />
            {blockData.block_type === 'open_ticket_linked' ? 'Duplicate Prevented — Linked to Open Incident' : 'Issue Already Resolved!'}
          </DialogTitle>
          <DialogContent>
            {blockData.block_type === 'open_ticket_linked' ? (
              <Box>
                <Alert severity="warning" icon={<GroupIcon fontSize="small" />} sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" fontWeight={800}>
                    {blockData.message}
                  </Typography>
                  <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                    No duplicate ticket was created. You have been added as a linked requester on Ticket #{blockData.ticket.id} (Total linked users: {blockData.ticket.requester_count}).
                  </Typography>
                </Alert>
              </Box>
            ) : (
              <Box>
                <Alert severity="success" icon={<CheckCircleOutlineIcon fontSize="small" />} sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" fontWeight={800}>
                    This issue was already resolved — Ticket #{blockData.ticket.id}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    {blockData.ticket.resolution_summary}
                  </Typography>
                </Alert>
              </Box>
            )}
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button
              variant="contained"
              fullWidth
              onClick={() => {
                setBlockDialogOpen(false)
                navigate('/dashboard')
              }}
              sx={{ bgcolor: '#2563EB', fontWeight: 700 }}
            >
              Return to Dashboard
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Box>
  )
}
