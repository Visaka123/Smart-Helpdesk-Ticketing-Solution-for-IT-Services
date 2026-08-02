import React, { useState } from 'react'
import {
  Box,
  Typography,
  Card,
  TextField,
  Button,
  Grid,
  Chip,
  Paper,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
  useTheme,
} from '@mui/material'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import SendIcon from '@mui/icons-material/Send'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import LockIcon from '@mui/icons-material/Lock'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import GroupIcon from '@mui/icons-material/Group'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

export default function CreateTicketPage() {
  const navigate = useNavigate()
  const theme = useTheme()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('General IT')
  const [department, setDepartment] = useState('Finance')
  const [requesterName, setRequesterName] = useState('Alice Employee')

  const [routingPreview, setRoutingPreview] = useState<any>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Hard Block Modal State
  const [blockDialogOpen, setBlockDialogOpen] = useState(false)
  const [blockData, setBlockData] = useState<any>(null)

  const handleDescBlur = async () => {
    if (description.trim().length < 15) return
    try {
      setPreviewLoading(true)
      const res = await axios.post(`${API_BASE}/ticket/route-ticket`, { description })
      setRoutingPreview(res.data)
    } catch (e) {
      console.error('Error fetching ML routing preview:', e)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!title.trim() || !description.trim()) {
      alert('Please fill in both title and description.')
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

      const res = await axios.post(`${API_BASE}/ticket/create`, {
        title,
        description,
        category,
        requester_name: requesterName,
        requester_department: department,
        skip_duplicate_check: false,
      }, { headers })

      if (res.data.is_hard_blocked) {
        setBlockData(res.data)
        setBlockDialogOpen(true)
        setSubmitting(false)
        return
      }

      alert('Ticket created successfully! ML routed to: ' + res.data.ticket.predicted_team)
      navigate('/dashboard')
    } catch (err) {
      console.error(err)
      alert('Error creating ticket')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box maxWidth={900} mx="auto">
      <Box mb={3}>
        <Typography variant="h2" fontWeight={800}>
          Submit Support Request
        </Typography>
        <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>
          Hybrid Semantic + Lexical Duplicate Prevention Engine & Hard-Block Auto-Linking.
        </Typography>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 3, bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}`, borderRadius: 2 }}>
            <Box display="flex" flexDirection="column" gap={2.5}>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <TextField
                    label="Your Name / User"
                    fullWidth
                    value={requesterName}
                    onChange={(e) => setRequesterName(e.target.value)}
                    placeholder="e.g. Alice Employee"
                  />
                </Grid>
                <Grid item xs={6}>
                  <TextField
                    select
                    label="Your Department"
                    fullWidth
                    value={department}
                    onChange={(e) => setDepartment(e.target.value)}
                    SelectProps={{ native: true }}
                  >
                    <option value="Finance">Finance</option>
                    <option value="Sales">Sales</option>
                    <option value="Engineering">Engineering</option>
                    <option value="Human Resources">Human Resources</option>
                  </TextField>
                </Grid>
              </Grid>

              <TextField
                label="Ticket Title / Subject"
                fullWidth
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. SAP Transaction SU53 Permission Error"
              />

              <TextField
                select
                label="Category"
                fullWidth
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                SelectProps={{ native: true }}
              >
                <option value="General IT">General IT</option>
                <option value="Network">Network & VPN</option>
                <option value="Database">Database & Storage</option>
                <option value="SAP Support">SAP & ERP</option>
                <option value="Security">Security & Access</option>
                <option value="HR Support">HR Systems</option>
              </TextField>

              <TextField
                label="Detailed Description"
                fullWidth
                multiline
                rows={5}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onBlur={handleDescBlur}
                placeholder="Describe your issue in detail..."
              />

              <Button
                variant="contained"
                size="large"
                disabled={submitting}
                onClick={handleSubmit}
                startIcon={<SendIcon />}
                style={{ backgroundColor: '#2563EB', padding: '10px 16px', fontWeight: 700 }}
              >
                {submitting ? 'Checking Duplicates...' : 'Submit Request'}
              </Button>
            </Box>
          </Paper>
        </Grid>

        {/* Real-time ML Preview */}
        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 3, bgcolor: theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A', border: `1px solid ${theme.palette.divider}`, borderRadius: 2 }}>
            <Box display="flex" alignItems="center" gap={1} mb={2}>
              <SmartToyIcon style={{ color: '#2563EB' }} />
              <Typography variant="h6" fontWeight={700}>
                Hybrid ML Duplicate Protection
              </Typography>
            </Box>

            {previewLoading ? (
              <Box display="flex" alignItems="center" gap={1} py={3}>
                <CircularProgress size={20} style={{ color: '#2563EB' }} />
                <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                  Computing hybrid semantic embeddings + lexical keyword overlap...
                </Typography>
              </Box>
            ) : routingPreview ? (
              <Box display="flex" flexDirection="column" gap={2}>
                <Box>
                  <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                    PREDICTED TEAM ROUTING:
                  </Typography>
                  <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                    <Chip
                      label={routingPreview.predicted_team}
                      color={routingPreview.is_low_confidence ? 'warning' : 'primary'}
                      style={{ fontWeight: 800 }}
                    />
                    <Typography variant="caption" style={{ color: '#10B981', fontWeight: 700 }}>
                      {routingPreview.confidence ? Math.round(routingPreview.confidence * 100) + '%' : 'Triage'} Confidence
                    </Typography>
                  </Box>
                </Box>
              </Box>
            ) : (
              <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>
                Enter your request details. Our hybrid engine prevents duplicate tickets by linking you directly to existing open issues or surfacing verified solutions.
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* HARD BLOCK DUPLICATE MODAL */}
      {blockData && (
        <Dialog open={blockDialogOpen} onClose={() => setBlockDialogOpen(false)} maxWidth="sm" fullWidth PaperProps={{ sx: { bgcolor: 'background.paper' } }}>
          <DialogTitle style={{ display: 'flex', alignItems: 'center', gap: 8, color: blockData.block_type === 'open_ticket_linked' ? '#D97706' : '#10B981' }}>
            <LockIcon style={{ color: blockData.block_type === 'open_ticket_linked' ? '#D97706' : '#10B981' }} />
            {blockData.block_type === 'open_ticket_linked' ? 'Duplicate Prevented — Linked to Open Incident' : 'Issue Already Resolved!'}
          </DialogTitle>
          <DialogContent>
            {blockData.block_type === 'open_ticket_linked' ? (
              <Box>
                <Alert severity="warning" icon={<GroupIcon fontSize="small" />} sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" fontWeight={800}>
                    {blockData.message}
                  </Typography>
                  <Typography variant="caption" style={{ display: 'block', marginTop: 4 }}>
                    No duplicate ticket was created. You have been added as a linked requester on Ticket #{blockData.ticket.id} (Total linked users: {blockData.ticket.requester_count}).
                  </Typography>
                </Alert>
                <Paper sx={{ p: 2, bgcolor: theme.palette.mode === 'light' ? '#FEF3C7' : '#2A1B14', border: '1px solid #FDE68A', borderRadius: 2 }}>
                  <Typography variant="caption" fontWeight={700} style={{ color: '#B45309' }}>SHARED MASTER TICKET #{blockData.ticket.id}:</Typography>
                  <Typography variant="body2" fontWeight={700} style={{ marginTop: 4 }}>{blockData.ticket.title}</Typography>
                  <Typography variant="caption" style={{ color: theme.palette.text.secondary, display: 'block', marginTop: 4 }}>
                    Status: {blockData.ticket.status.toUpperCase()} | Assigned Team: {blockData.ticket.assigned_team}
                  </Typography>
                </Paper>
              </Box>
            ) : (
              <Box>
                {/* Resolved ticket — prominent banner */}
                <Box sx={{ bgcolor: '#ECFDF5', border: '2px solid #10B981', borderRadius: 2, p: 2, mb: 2, display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                  <CheckCircleIcon style={{ color: '#10B981', fontSize: 32, marginTop: 2 }} />
                  <Box>
                    <Typography variant="subtitle1" fontWeight={800} style={{ color: '#065F46' }}>
                      This issue has already been resolved!
                    </Typography>
                    <Typography variant="body2" style={{ color: '#047857', marginTop: 2 }}>
                      Ticket #{blockData.ticket.id} — <strong>{blockData.ticket.title}</strong>
                    </Typography>
                    <Typography variant="caption" style={{ color: '#6B7280', display: 'block', marginTop: 2 }}>
                      No new ticket was created. The verified fix is shown below.
                    </Typography>
                  </Box>
                </Box>

                <Paper sx={{ p: 2.5, bgcolor: theme.palette.mode === 'light' ? '#F0FDF4' : '#052e16', border: '1px solid #A7F3D0', borderRadius: 2 }}>
                  <Typography variant="overline" fontWeight={700} style={{ color: '#047857', letterSpacing: 1 }}>
                    Verified Resolution
                  </Typography>
                  <Typography variant="body1" style={{ color: theme.palette.mode === 'light' ? '#1E293B' : '#d1fae5', whiteSpace: 'pre-line', marginTop: 8, lineHeight: 1.7 }}>
                    {blockData.ticket.resolution_summary || 'Resolution details are available from the support team.'}
                  </Typography>

                  {blockData.ticket.resolution_detail && (
                    <Accordion sx={{ bgcolor: 'transparent', boxShadow: 'none', mt: 1.5, border: '1px solid #A7F3D0', borderRadius: '8px !important' }}>
                      <AccordionSummary expandIcon={<ExpandMoreIcon fontSize="small" />}>
                        <Typography variant="caption" style={{ color: '#2563EB', fontWeight: 700 }}>
                          View Technical Steps & Fix Details
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Typography variant="caption" style={{ fontFamily: 'monospace', whiteSpace: 'pre-line', color: theme.palette.mode === 'light' ? '#1E293B' : '#d1fae5', lineHeight: 1.8 }}>
                          {blockData.ticket.resolution_detail}
                        </Typography>
                      </AccordionDetails>
                    </Accordion>
                  )}
                </Paper>

                <Typography variant="caption" style={{ color: '#9CA3AF', display: 'block', marginTop: 8, textAlign: 'center' }}>
                  Resolved by: {blockData.ticket.assigned_team || 'Support Team'}
                </Typography>
              </Box>
            )}
          </DialogContent>
          <DialogActions style={{ padding: 16 }}>
            <Button
              variant="contained"
              style={{ backgroundColor: '#2563EB', fontWeight: 700 }}
              fullWidth
              onClick={() => {
                setBlockDialogOpen(false)
                navigate('/dashboard')
              }}
            >
              Return to Dashboard
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Box>
  )
}
