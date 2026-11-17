import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, useOutletContext } from 'react-router-dom'
import {
  Box, Typography, Card, CardContent, Grid, Chip, Button, CircularProgress,
  Alert, Divider, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Select, MenuItem, FormControl, InputLabel, Tooltip,
  Paper, useTheme,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import SwapHorizIcon from '@mui/icons-material/SwapHoriz'
import PersonIcon from '@mui/icons-material/Person'
import HistoryIcon from '@mui/icons-material/History'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import DownloadIcon from '@mui/icons-material/Download'
import DescriptionIcon from '@mui/icons-material/Description'
import axios from 'axios'
import { availabilityApi, attachmentApi } from '../api/services'
import { PriorityBadge, StatusBadge, SLABadge } from '../components/ui/SemanticBadges'
import { AvailabilityBadge, getAvailStatus } from '../components/ui/AvailabilityBadge'
import type { AssignmentLogEntry, AgentAvailability, TicketAttachment } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

function fmtDate(s: string) {
  if (!s) return '—'
  try {
    const d = new Date(s.includes('T') ? s : s.replace(' ', 'T'))
    if (isNaN(d.getTime())) return s
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(d)
  } catch {
    return s
  }
}

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const ticketId = Number(id)
  const navigate = useNavigate()
  const theme = useTheme()
  const context = useOutletContext<{ currentRole?: string }>()
  const currentRole = context?.currentRole || 'employee'
  const isPrivileged = currentRole === 'manager' || currentRole === 'team_lead' || currentRole === 'admin'

  const [ticket, setTicket] = useState<any>(null)
  const [logs, setLogs] = useState<AssignmentLogEntry[]>([])
  const [agents, setAgents] = useState<AgentAvailability[]>([])
  const [attachments, setAttachments] = useState<TicketAttachment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Reassign modal
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState('')
  const [overrideReason, setOverrideReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const storedUser = localStorage.getItem('user')
  const callerName = storedUser ? (() => { try { return JSON.parse(storedUser).name || 'Manager' } catch { return 'Manager' } })() : 'Manager'

  // Fetch ticket + assignment log — does NOT include the slow agents call
  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const token = localStorage.getItem('token')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (storedUser) {
        try {
          const u = JSON.parse(storedUser)
          headers['X-User-Id'] = String(u.id)
          headers['X-User-Role'] = currentRole
          headers['X-User-Email'] = u.email
          headers['X-User-Name'] = u.name
        } catch {}
      }
      const [tRes, lRes, aRes] = await Promise.all([
        axios.get(`${API_BASE}/ticket/all`, { headers }),
        availabilityApi.getAssignmentLog(ticketId),
        attachmentApi.getByTicket(ticketId).catch(() => ({ data: [] })),
      ])
      const found = Array.isArray(tRes.data) ? tRes.data.find((t: any) => t.id === ticketId) : null
      if (!found) { setError('Ticket not found.'); return }
      setTicket(found)
      setLogs(Array.isArray(lRes.data) ? lRes.data : [])
      setAttachments(Array.isArray(aRes.data) ? aRes.data : [])
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load ticket.')
    } finally {
      setLoading(false)
    }
  }, [ticketId, currentRole])

  // Lazily fetch agents only when the reassign modal is opened
  const [agentsLoading, setAgentsLoading] = useState(false)
  const fetchAgents = useCallback(async () => {
    if (!isPrivileged) return
    setAgentsLoading(true)
    try {
      const aRes = await availabilityApi.getAvailableNow()
      setAgents(Array.isArray(aRes.data) ? aRes.data : [])
    } catch {
      // non-fatal
    } finally {
      setAgentsLoading(false)
    }
  }, [isPrivileged])

  useEffect(() => { fetchAll() }, [fetchAll])

  const openReassignModal = () => {
    setModalOpen(true)
    if (agents.length === 0) fetchAgents()  // lazy load on first open
  }

  const handleReassign = async () => {
    if (!selectedAgent || !overrideReason.trim()) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      await availabilityApi.override(ticketId, selectedAgent, callerName + ' — ' + overrideReason.trim())
      setModalOpen(false)
      setSelectedAgent('')
      setOverrideReason('')
      await fetchAll()
    } catch (e: any) {
      setSubmitError(e?.response?.data?.detail || 'Reassignment failed.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return (
    <Box display="flex" justifyContent="center" alignItems="center" minHeight={300}>
      <CircularProgress style={{ color: '#2563EB' }} />
    </Box>
  )

  if (error) return (
    <Box>
      <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mb: 2 }}>Back</Button>
      <Alert severity="error">{error}</Alert>
    </Box>
  )

  if (!ticket) return null

  const currentLog = logs[0]

  return (
    <Box>
      {/* Page header */}
      <Box display="flex" alignItems="center" gap={1.5} mb={3}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} size="small"
          style={{ color: theme.palette.text.secondary }}>
          Back
        </Button>
        <Typography variant="h2" fontWeight={800} flexGrow={1}>
          #{ticket.id} — {ticket.title}
        </Typography>
        <PriorityBadge priority={ticket.priority} size="medium" />
        <StatusBadge status={ticket.status} size="medium" />
        {ticket.sla_badge && <SLABadge badge={ticket.sla_badge} size="medium" />}
      </Box>

      <Grid container spacing={3}>
        {/* Left: ticket info */}
        <Grid item xs={12} md={7}>
          <Card>
            <CardContent>
              <Typography variant="h5" fontWeight={700} mb={1}>Ticket Details</Typography>
              <Divider sx={{ mb: 2 }} />
              <Typography variant="body1" mb={2} style={{ color: theme.palette.text.primary }}>
                {ticket.description}
              </Typography>
              <Box display="flex" flexWrap="wrap" gap={1.5}>
                <Chip label={ticket.category || 'General IT'} size="small"
                  style={{ backgroundColor: theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B', color: '#2563EB', fontWeight: 700 }} />
                {ticket.assigned_team && (
                  <Chip label={`Team: ${ticket.assigned_team}`} size="small"
                    style={{ backgroundColor: theme.palette.mode === 'light' ? '#F1F5F9' : '#0F172A', fontWeight: 600 }} />
                )}
              </Box>
              <Box mt={2} display="flex" flexDirection="column" gap={0.5}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                  Requester: <strong>{ticket.requester_name || '—'}</strong>
                </Typography>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                  Created: <strong>{fmtDate(ticket.created_at)}</strong>
                </Typography>
                {ticket.sla_due_at && (
                  <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                    SLA due: <strong>{fmtDate(ticket.sla_due_at)}</strong>
                  </Typography>
                )}
              </Box>

              {/* Attachments */}
              {attachments.length > 0 && (
                <Box mt={2.5}>
                  <Box display="flex" alignItems="center" gap={0.8} mb={1}>
                    <AttachFileIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                    <Typography variant="caption" fontWeight={700} color="text.secondary">
                      ATTACHED DOCUMENTS ({attachments.length}):
                    </Typography>
                  </Box>
                  <Grid container spacing={1.5}>
                    {attachments.map((att) => (
                      <Grid item xs={12} sm={6} key={att.id}>
                        <Paper
                          variant="outlined"
                          sx={{
                            p: 1.2,
                            px: 1.5,
                            borderRadius: 2,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 1,
                          }}
                        >
                          <Box display="flex" alignItems="center" gap={1} sx={{ minWidth: 0 }}>
                            <DescriptionIcon sx={{ color: '#2563EB', fontSize: 20 }} />
                            <Box sx={{ minWidth: 0 }}>
                              <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: { xs: 140, sm: 200 } }}>
                                {att.filename}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {att.formatted_size || `${(att.file_size / 1024).toFixed(1)} KB`}
                              </Typography>
                            </Box>
                          </Box>
                          <Button
                            size="small"
                            variant="outlined"
                            href={`${API_BASE}${att.download_url}`}
                            target="_blank"
                            download
                            startIcon={<DownloadIcon style={{ fontSize: 13 }} />}
                            sx={{ textTransform: 'none', fontSize: '0.72rem', px: 1.2, py: 0.3, flexShrink: 0 }}
                          >
                            Download
                          </Button>
                        </Paper>
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Right: assignment card */}
        <Grid item xs={12} md={5}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                <Typography variant="h5" fontWeight={700} display="flex" alignItems="center" gap={1}>
                  <PersonIcon fontSize="small" style={{ color: '#2563EB' }} />
                  Assignment
                </Typography>
                {isPrivileged && (
                  <Tooltip title="Manually reassign this ticket">
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<SwapHorizIcon />}
                      onClick={openReassignModal}
                      style={{ borderColor: '#2563EB', color: '#2563EB' }}
                    >
                      Reassign
                    </Button>
                  </Tooltip>
                )}
              </Box>
              <Divider sx={{ mb: 2 }} />

              {ticket.assigned_agent_name ? (
                <Box>
                  <Typography variant="body2" fontWeight={700} style={{ color: theme.palette.text.primary }}>
                    {ticket.assigned_agent_name}
                  </Typography>
                  {(() => {
                    const agent = agents.find(a => a.name === ticket.assigned_agent_name)
                    if (agent) {
                      const status = getAvailStatus(agent)
                      return (
                        <Box mt={0.5} display="flex" alignItems="center" gap={1}>
                          <AvailabilityBadge status={status} />
                          <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                            {agent.open_tickets}/{agent.ticket_cap} tickets · {agent.timezone}
                          </Typography>
                        </Box>
                      )
                    }
                    return null
                  })()}
                  {currentLog && (
                    <Paper variant="outlined" sx={{ mt: 1.5, p: 1.5, bgcolor: theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A' }}>
                      <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontStyle: 'italic' }}>
                        "{currentLog.reason}"
                      </Typography>
                    </Paper>
                  )}
                </Box>
              ) : (
                <Alert severity="warning" sx={{ mt: 1 }}>
                  No agent currently assigned.
                </Alert>
              )}

              {/* Assignment timeline */}
              {logs.length > 0 && (
                <Box mt={3}>
                  <Typography variant="caption" fontWeight={700} display="flex" alignItems="center" gap={0.5}
                    style={{ color: theme.palette.text.secondary, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    <HistoryIcon style={{ fontSize: 14 }} /> Assignment History
                  </Typography>
                  <Box mt={1} display="flex" flexDirection="column" gap={0}>
                    {logs.map((log, i) => (
                      <Box key={log.id} display="flex" gap={1.5} position="relative">
                        {/* Timeline line */}
                        <Box display="flex" flexDirection="column" alignItems="center" minWidth={16}>
                          <Box width={10} height={10} borderRadius="50%"
                            bgcolor={i === 0 ? '#2563EB' : theme.palette.divider}
                            border={`2px solid ${i === 0 ? '#2563EB' : theme.palette.text.disabled}`}
                            mt={0.5} flexShrink={0}
                            role="img" aria-label={i === 0 ? 'Current assignment' : 'Past assignment'}
                          />
                          {i < logs.length - 1 && (
                            <Box width={2} flexGrow={1} bgcolor={theme.palette.divider} my={0.25} />
                          )}
                        </Box>
                        <Box pb={1.5}>
                          <Typography variant="caption" fontWeight={700} style={{ color: theme.palette.text.primary }}>
                            {log.assigned_to || 'Unassigned'}
                            {log.override_by && (
                              <Chip label={`Override by ${log.override_by}`} size="small"
                                style={{ marginLeft: 6, fontSize: '0.65rem', height: 16, backgroundColor: '#EDE9FE', color: '#6D28D9' }} />
                            )}
                            {log.fallback && (
                              <Chip label={log.fallback} size="small"
                                style={{ marginLeft: 6, fontSize: '0.65rem', height: 16, backgroundColor: '#FEF3C7', color: '#B45309' }} />
                            )}
                          </Typography>
                          <Typography variant="caption" display="block" style={{ color: theme.palette.text.secondary }}>
                            {fmtDate(log.at)}
                          </Typography>
                          <Typography variant="caption" display="block"
                            style={{ color: theme.palette.text.secondary, fontStyle: 'italic', maxWidth: 280 }}>
                            {log.reason}
                          </Typography>
                        </Box>
                      </Box>
                    ))}
                  </Box>
                </Box>
              )}

              {logs.length === 0 && (
                <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                  No assignment history yet.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Reassign Modal */}
      <Dialog open={modalOpen} onClose={() => setModalOpen(false)} maxWidth="sm" fullWidth
        aria-labelledby="reassign-dialog-title">
        <DialogTitle id="reassign-dialog-title">
          Reassign Ticket #{ticketId}
        </DialogTitle>
        <DialogContent>
          {submitError && <Alert severity="error" sx={{ mb: 2 }}>{submitError}</Alert>}
          <FormControl fullWidth sx={{ mt: 1, mb: 2 }}>
            <InputLabel id="agent-select-label">New Agent</InputLabel>
            <Select
              labelId="agent-select-label"
              value={selectedAgent}
              label="New Agent"
              onChange={(e) => setSelectedAgent(e.target.value)}
            >
              {agentsLoading && (
                <MenuItem disabled value="">
                  <CircularProgress size={14} sx={{ mr: 1 }} /> Loading agents…
                </MenuItem>
              )}
              {!agentsLoading && agents.length === 0 && (
                <MenuItem disabled value="">No agents available. Try refreshing.</MenuItem>
              )}
              {agents.map((a) => {
                const status = getAvailStatus(a)
                const isOnLeave = status === 'on_leave'
                return (
                  <MenuItem key={a.id} value={a.name} disabled={isOnLeave}>
                    <Box display="flex" alignItems="center" gap={1.5} width="100%">
                      <AvailabilityBadge status={status} />
                      <Box flexGrow={1}>
                        <Typography variant="body2" fontWeight={600}>
                          {a.name} {isOnLeave ? '(On Leave)' : ''}
                        </Typography>
                        <Typography variant="caption" style={{ color: '#64748B' }}>
                          {a.team} · {a.open_tickets}/{a.ticket_cap} open · {a.timezone}
                        </Typography>
                      </Box>
                    </Box>
                  </MenuItem>
                )
              })}
            </Select>
          </FormControl>
          <TextField
            label="Reason for reassignment *"
            fullWidth
            multiline
            minRows={2}
            value={overrideReason}
            onChange={(e) => setOverrideReason(e.target.value)}
            placeholder="e.g. Agent going on leave, escalation required…"
            inputProps={{ 'aria-required': true }}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setModalOpen(false)} disabled={submitting}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleReassign}
            disabled={submitting || !selectedAgent || !overrideReason.trim()}
            style={{ backgroundColor: '#2563EB' }}
          >
            {submitting ? <CircularProgress size={16} style={{ color: '#fff' }} /> : 'Reassign'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
