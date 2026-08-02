import React, { useState, useEffect } from 'react'
import {
  Box,
  Typography,
  Grid,
  Card,
  Chip,
  Button,
  Paper,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Tabs,
  Tab,
  Select,
  MenuItem,
  Alert,
  Tooltip,
  FormControl,
  InputLabel,
  useTheme,
} from '@mui/material'
import SupportAgentIcon from '@mui/icons-material/SupportAgent'
import GroupIcon from '@mui/icons-material/Group'
import CallSplitIcon from '@mui/icons-material/CallSplit'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import LockIcon from '@mui/icons-material/Lock'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import axios from 'axios'

import { PriorityBadge, SLABadge, StatusBadge } from '../components/ui/SemanticBadges'
import { ITSMTimeline } from '../components/ui/ITSMTimeline'
import { KnowledgeRecommendationPanel } from '../components/ui/KnowledgeRecommendationPanel'

const API_BASE = 'http://localhost:8000'

export default function AgentPortalPage() {
  const theme = useTheme()
  const [tabValue, setTabValue] = useState(0)
  const [tickets, setTickets] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [managerData, setManagerData] = useState<any>(null)

  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null)
  const [ticketDetail, setTicketDetail] = useState<any>(null)
  const [recommendations, setRecommendations] = useState<any[]>([])
  const [detailOpen, setDetailOpen] = useState(false)

  // Agent Workspace UI state
  const [showResolveForm, setShowResolveForm] = useState(false)

  // Inline Controls State
  const [currentPriority, setCurrentPriority] = useState('Medium')
  const [currentStatus, setCurrentStatus] = useState('open')
  const [currentTeam, setCurrentTeam] = useState('IT Support')
  const [assignedEngineer, setAssignedEngineer] = useState('Sarah Agent')

  // Comments
  const [commentText, setCommentText] = useState('')
  const [isInternal, setIsInternal] = useState(false)

  // Structured Resolution Form
  const [resolutionSummary, setResolutionSummary] = useState('')
  const [resolutionDetail, setResolutionDetail] = useState('')
  const [rootCause, setRootCause] = useState('User Error')

  const fetchAgentQueue = async () => {
    try {
      const token = localStorage.getItem('token')
      const storedUser = localStorage.getItem('user')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (storedUser) {
        try {
          const u = JSON.parse(storedUser)
          headers['X-User-Id'] = String(u.id)
          headers['X-User-Role'] = 'agent'
          headers['X-User-Email'] = u.email
        } catch (e) {}
      } else {
        headers['X-User-Role'] = 'agent'
      }

      const [qRes, sRes, mRes] = await Promise.all([
        axios.get(`${API_BASE}/agent/queue`, { headers }),
        axios.get(`${API_BASE}/agent/agent-stats`, { headers }),
        axios.get(`${API_BASE}/agent/manager-dashboard`, { headers }),
      ])
      setTickets(qRes.data)
      setStats(sRes.data)
      setManagerData(mRes.data)
    } catch (e) {
      console.error('Error fetching agent queue:', e)
    }
  }

  useEffect(() => {
    fetchAgentQueue()
  }, [])

  const openTicketDetail = async (id: number) => {
    setSelectedTicketId(id)
    setShowResolveForm(false)
    try {
      const token = localStorage.getItem('token')
      const storedUser = localStorage.getItem('user')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (storedUser) {
        try {
          const u = JSON.parse(storedUser)
          headers['X-User-Id'] = String(u.id)
          headers['X-User-Role'] = 'agent'
          headers['X-User-Email'] = u.email
        } catch (e) {}
      } else {
        headers['X-User-Role'] = 'agent'
      }

      const res = await axios.get(`${API_BASE}/agent/detail/${id}`, { headers })
      setTicketDetail(res.data)
      setCurrentPriority(res.data.priority || 'Medium')
      setCurrentStatus(res.data.status || 'open')
      setCurrentTeam(res.data.assigned_team || 'Unassigned/Triage')
      setAssignedEngineer(res.data.assigned_agent_name || 'Sarah Agent')
      setResolutionSummary(res.data.resolution_summary || '')
      setResolutionDetail(res.data.resolution_detail || '')
      setRootCause(res.data.root_cause || 'User Error')
      setDetailOpen(true)

      if (res.data.status === 'resolved' || res.data.status === 'closed') {
        setShowResolveForm(true)
      }

      // Fetch proactive KB & SOP recommendations
      try {
        const recRes = await axios.post(`${API_BASE}/chatbot/recommendations`, {
          title: res.data.title,
          description: res.data.description,
        })
        setRecommendations(recRes.data.recommended_articles || [])
      } catch (err) {
        console.error('Error fetching recommendations:', err)
        setRecommendations([])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const [submittingComment, setSubmittingComment] = useState(false)
  const [submittingResolve, setSubmittingResolve] = useState(false)
  const [submittingAction, setSubmittingAction] = useState(false)

  const handleInlineAssignTeam = async (ticketId: number, newTeam: string) => {
    if (newTeam === currentTeam || submittingAction) return
    try {
      setSubmittingAction(true)
      await axios.post(`${API_BASE}/agent/assign-team/${ticketId}`, { new_team: newTeam })
      setCurrentTeam(newTeam)
      fetchAgentQueue()
    } catch (e) {
      console.error(e)
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleChangePriority = async (newPriority: string) => {
    if (!selectedTicketId || newPriority === currentPriority || submittingAction) return
    try {
      setSubmittingAction(true)
      await axios.post(`${API_BASE}/agent/change-priority/${selectedTicketId}`, { new_priority: newPriority })
      setCurrentPriority(newPriority)
      openTicketDetail(selectedTicketId)
      fetchAgentQueue()
    } catch (e) {
      console.error(e)
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleChangeStatus = async (newStatus: string) => {
    if (!selectedTicketId || newStatus === currentStatus || submittingAction) return
    setCurrentStatus(newStatus)
    if (newStatus === 'resolved' || newStatus === 'closed') {
      setShowResolveForm(true)
    } else {
      try {
        setSubmittingAction(true)
        await axios.post(`${API_BASE}/agent/change-status/${selectedTicketId}`, { new_status: newStatus })
        openTicketDetail(selectedTicketId)
        fetchAgentQueue()
      } catch (e) {
        console.error(e)
      } finally {
        setSubmittingAction(false)
      }
    }
  }

  const handleAssignEngineer = async (agentName: string) => {
    if (!selectedTicketId || agentName === assignedEngineer || submittingAction) return
    try {
      setSubmittingAction(true)
      await axios.post(`${API_BASE}/agent/assign-engineer/${selectedTicketId}`, { agent_name: agentName })
      setAssignedEngineer(agentName)
      openTicketDetail(selectedTicketId)
      fetchAgentQueue()
    } catch (e) {
      console.error(e)
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleSplitRequester = async (requesterName: string) => {
    if (!selectedTicketId || submittingAction) return
    const reason = prompt(`Reason for un-linking '${requesterName}' into a separate standalone ticket:`, 'Distinct issue un-merged by agent')
    if (!reason) return

    try {
      setSubmittingAction(true)
      const res = await axios.post(`${API_BASE}/agent/split-requester/${selectedTicketId}`, {
        requester_name: requesterName,
        reason,
      })
      alert(`Requester '${requesterName}' un-linked into new standalone Ticket #${res.data.new_ticket_id}!`)
      openTicketDetail(selectedTicketId)
      fetchAgentQueue()
    } catch (e) {
      console.error(e)
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleResolve = async () => {
    if (!selectedTicketId || !resolutionSummary.trim() || submittingResolve) {
      if (!resolutionSummary.trim()) alert('Resolution summary (plain language) is required to resolve a ticket.')
      return
    }
    try {
      setSubmittingResolve(true)
      const res = await axios.post(`${API_BASE}/agent/resolve/${selectedTicketId}`, {
        resolution_summary: resolutionSummary,
        resolution_detail: resolutionDetail || resolutionSummary,
        root_cause: rootCause,
      })
      alert(`Ticket #${selectedTicketId} resolved for all ${res.data.resolved_requesters.length} linked requesters!`)
      openTicketDetail(selectedTicketId)
      fetchAgentQueue()
    } catch (e) {
      console.error(e)
    } finally {
      setSubmittingResolve(false)
    }
  }

  const handleAddComment = async () => {
    if (!selectedTicketId || !commentText.trim() || submittingComment) return
    try {
      setSubmittingComment(true)
      await axios.post(`${API_BASE}/agent/comment/${selectedTicketId}`, {
        content: commentText,
        author_name: 'Support Agent',
        author_role: 'agent',
        is_internal: isInternal,
      })
      setCommentText('')
      openTicketDetail(selectedTicketId)
    } catch (e) {
      console.error(e)
    } finally {
      setSubmittingComment(false)
    }
  }

  const isClosed = ticketDetail && ticketDetail.status === 'closed'

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box display="flex" alignItems="center" gap={1.5}>
          <SupportAgentIcon style={{ color: '#2563EB', fontSize: 32 }} />
          <Box>
            <Typography variant="h2" fontWeight={800}>
              Agent & Manager ITSM Workspace
            </Typography>
            <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>
              Enterprise Queue with Multi-Format SOP RAG Recommendations, ITSM Audit Timeline & Linked Requesters
            </Typography>
          </Box>
        </Box>
      </Box>

      <Box borderBottom={1} borderColor="divider" mb={3}>
        <Tabs value={tabValue} onChange={(_, val) => setTabValue(val)} indicatorColor="primary" textColor="primary">
          <Tab label="Agent Ticket Queue" style={{ fontWeight: 700 }} />
          <Tab label="Manager SLA Escalation Center" style={{ fontWeight: 700 }} />
        </Tabs>
      </Box>

      {tabValue === 0 ? (
        <Box>
          <Grid container spacing={2} mb={3}>
            <Grid item xs={12} sm={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                  RESOLVED TICKETS
                </Typography>
                <Typography variant="h4" fontWeight={800} style={{ color: '#10B981', marginTop: 4 }}>
                  {stats?.tickets_resolved || 0}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                  SLA COMPLIANCE
                </Typography>
                <Typography variant="h4" fontWeight={800} style={{ color: '#2563EB', marginTop: 4 }}>
                  {stats?.sla_compliance_pct || 100}%
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                  AVG RESOLUTION TIME
                </Typography>
                <Typography variant="h4" fontWeight={800} style={{ color: '#D97706', marginTop: 4 }}>
                  {stats?.avg_resolution_hours || 3.4} hrs
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                  ACTIVE BREACHED
                </Typography>
                <Typography variant="h4" fontWeight={800} style={{ color: '#DC2626', marginTop: 4 }}>
                  {stats?.breached_count || 0}
                </Typography>
              </Paper>
            </Grid>
          </Grid>

          {/* Ticket Queue Table */}
          <Paper sx={{ bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Subject</TableCell>
                  <TableCell>Priority</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>SLA Status</TableCell>
                  <TableCell>Linked Requesters</TableCell>
                  <TableCell>Team Assign</TableCell>
                  <TableCell>Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {tickets.map((t) => (
                  <TableRow key={t.id} hover>
                    <TableCell style={{ fontWeight: 700, color: '#2563EB' }}>#{t.id}</TableCell>
                    <TableCell style={{ fontWeight: 600, color: theme.palette.text.primary }}>
                      {t.title}
                    </TableCell>
                    <TableCell><PriorityBadge priority={t.priority} /></TableCell>
                    <TableCell><StatusBadge status={t.status} /></TableCell>
                    <TableCell><SLABadge badge={t.sla_badge} /></TableCell>
                    <TableCell>
                      <Chip
                        icon={<GroupIcon style={{ fontSize: 14 }} />}
                        label={`${t.requester_count} User${t.requester_count > 1 ? 's' : ''}`}
                        size="small"
                        style={{ backgroundColor: t.requester_count > 1 ? '#FEF3C7' : '#EFF6FF', color: t.requester_count > 1 ? '#B45309' : '#2563EB', fontWeight: 700 }}
                      />
                    </TableCell>
                    <TableCell>
                      <Select
                        size="small"
                        value={t.assigned_team || 'Unassigned/Triage'}
                        onChange={(e) => handleInlineAssignTeam(t.id, e.target.value)}
                        sx={{ fontSize: '0.78rem', height: 32, minWidth: 150 }}
                      >
                        <MenuItem value="Unassigned/Triage">⚠️ Unassigned/Triage</MenuItem>
                        <MenuItem value="IT Support">IT Support</MenuItem>
                        <MenuItem value="Network Team">Network Team</MenuItem>
                        <MenuItem value="Database Team">Database Team</MenuItem>
                        <MenuItem value="Security Team">Security Team</MenuItem>
                        <MenuItem value="SAP Team">SAP Team</MenuItem>
                        <MenuItem value="HR Support">HR Support</MenuItem>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Button variant="contained" size="small" style={{ backgroundColor: '#2563EB' }} onClick={() => openTicketDetail(t.id)}>
                        Open Workspace
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>
        </Box>
      ) : (
        <Box>
          <Grid container spacing={3} mb={3}>
            <Grid item xs={12} md={4}>
              <Card sx={{ bgcolor: 'background.paper', p: 3 }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                  OVERALL SLA COMPLIANCE
                </Typography>
                <Typography variant="h2" fontWeight={800} style={{ color: '#10B981', marginTop: 8 }}>
                  {managerData?.overall_sla_compliance || 100}%
                </Typography>
              </Card>
            </Grid>
            <Grid item xs={12} md={4}>
              <Card sx={{ bgcolor: 'background.paper', p: 3 }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                  AT-RISK TICKETS
                </Typography>
                <Typography variant="h2" fontWeight={800} style={{ color: '#D97706', marginTop: 8 }}>
                  {managerData?.at_risk_tickets || 0}
                </Typography>
              </Card>
            </Grid>
            <Grid item xs={12} md={4}>
              <Card sx={{ bgcolor: 'background.paper', p: 3 }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                  TOTAL SLA BREACHES
                </Typography>
                <Typography variant="h2" fontWeight={800} style={{ color: '#DC2626', marginTop: 8 }}>
                  {managerData?.breached_tickets || 0}
                </Typography>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Ticket Detail Workspace Modal */}
      {ticketDetail && (
        <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} maxWidth="lg" fullWidth PaperProps={{ sx: { bgcolor: 'background.paper', borderRadius: 3 } }}>
          <DialogTitle style={{ borderBottom: `1px solid ${theme.palette.divider}`, padding: '16px 24px' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center">
              <Box display="flex" alignItems="center" gap={1.5}>
                <Typography variant="h5" fontWeight={800}>
                  Ticket #{ticketDetail.id}: {ticketDetail.title}
                </Typography>
                <StatusBadge status={ticketDetail.status} />
                {isClosed && (
                  <Chip icon={<LockIcon style={{ fontSize: 14 }} />} label="Read-Only Workspace (Closed)" color="secondary" size="small" style={{ fontWeight: 700 }} />
                )}
              </Box>
              <SLABadge badge={ticketDetail.sla_badge} />
            </Box>
          </DialogTitle>

          <DialogContent style={{ paddingTop: 20 }}>
            {/* WORKSPACE AGENT CONTROLS BAR */}
            <Paper elevation={0} sx={{ p: 2, bgcolor: theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A', border: `1px solid ${theme.palette.divider}`, borderRadius: 2, mb: 2.5 }}>
              <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} sm={3}>
                  <FormControl fullWidth size="small" disabled={isClosed}>
                    <InputLabel>Status</InputLabel>
                    <Select value={currentStatus} label="Status" onChange={(e) => handleChangeStatus(e.target.value)}>
                      <MenuItem value="open">Open</MenuItem>
                      <MenuItem value="in_progress">In Progress</MenuItem>
                      <MenuItem value="on_hold">On Hold</MenuItem>
                      <MenuItem value="resolved">Resolved</MenuItem>
                      <MenuItem value="closed">Closed</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} sm={3}>
                  <FormControl fullWidth size="small" disabled={isClosed}>
                    <InputLabel>Priority</InputLabel>
                    <Select value={currentPriority} label="Priority" onChange={(e) => handleChangePriority(e.target.value)}>
                      <MenuItem value="Low">Low</MenuItem>
                      <MenuItem value="Medium">Medium</MenuItem>
                      <MenuItem value="High">High</MenuItem>
                      <MenuItem value="Critical">Critical</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} sm={3}>
                  <FormControl fullWidth size="small" disabled={isClosed}>
                    <InputLabel>Team Assignment</InputLabel>
                    <Select value={currentTeam} label="Team Assignment" onChange={(e) => handleInlineAssignTeam(ticketDetail.id, e.target.value)}>
                      <MenuItem value="Unassigned/Triage">⚠️ Unassigned/Triage</MenuItem>
                      <MenuItem value="IT Support">IT Support</MenuItem>
                      <MenuItem value="Network Team">Network Team</MenuItem>
                      <MenuItem value="Database Team">Database Team</MenuItem>
                      <MenuItem value="Security Team">Security Team</MenuItem>
                      <MenuItem value="SAP Team">SAP Team</MenuItem>
                      <MenuItem value="HR Support">HR Support</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} sm={3}>
                  <TextField
                    label="Assigned Engineer"
                    fullWidth
                    size="small"
                    disabled={isClosed}
                    value={assignedEngineer}
                    onChange={(e) => setAssignedEngineer(e.target.value)}
                    onBlur={(e) => handleAssignEngineer(e.target.value)}
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Triage Explanation if low confidence */}
            {ticketDetail.triage_explanation && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                <Typography variant="caption">{ticketDetail.triage_explanation}</Typography>
              </Alert>
            )}

            {/* LINKED REQUESTERS PANEL WITH SPLIT ACTION */}
            <Paper sx={{ p: 2, bgcolor: theme.palette.mode === 'light' ? '#EFF6FF' : '#0F172A', border: '1px solid #BFDBFE', borderRadius: 2, mb: 2.5 }}>
              <Typography variant="caption" fontWeight={800} style={{ color: '#2563EB', display: 'flex', alignItems: 'center', gap: 6 }}>
                <GroupIcon fontSize="small" />
                LINKED REQUESTERS ({ticketDetail.requester_count} USERS HARDBLOCKED & LINKED TO THIS TICKET):
              </Typography>
              <Box display="flex" gap={1} flexWrap="wrap" mt={1}>
                {ticketDetail.linked_requesters?.map((req: any, idx: number) => (
                  <Chip
                    key={idx}
                    label={`${req.name} (${req.department}) ${req.is_primary ? ' [Primary]' : ''}`}
                    size="small"
                    color={req.is_primary ? 'primary' : 'default'}
                    style={{ fontWeight: 600 }}
                    onDelete={!req.is_primary && !isClosed ? () => handleSplitRequester(req.name) : undefined}
                    deleteIcon={
                      <Tooltip title="Un-link & Split into standalone Ticket">
                        <CallSplitIcon style={{ fontSize: 14 }} />
                      </Tooltip>
                    }
                  />
                ))}
              </Box>
            </Paper>

            {/* PROACTIVE KNOWLEDGE & SOP RECOMMENDATIONS */}
            {recommendations.length > 0 && (
              <KnowledgeRecommendationPanel articles={recommendations} />
            )}

            {/* SIMILAR RESOLVED TICKETS */}
            {ticketDetail.similar_tickets && ticketDetail.similar_tickets.length > 0 && (
              <Paper sx={{ p: 2, bgcolor: theme.palette.mode === 'light' ? '#FFFBEB' : '#2A1B14', border: '1px solid #FDE68A', borderRadius: 2, mb: 2.5 }}>
                <Typography variant="caption" fontWeight={800} style={{ color: '#B45309', display: 'block', mb: 1 }}>
                  SIMILAR RESOLVED INCIDENTS (HYBRID MATCH):
                </Typography>
                <Box display="flex" flexDirection="column" gap={1}>
                  {ticketDetail.similar_tickets.map((st: any) => (
                    <Box key={st.id} display="flex" justifyContent="space-between" alignItems="center">
                      <Typography variant="caption" fontWeight={700} style={{ color: '#92400E' }}>
                        #{st.id} - {st.title} (Match: {Math.round(st.similarity_score * 100)}%)
                      </Typography>
                      {st.resolution_summary && (
                        <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontStyle: 'italic' }}>
                          Fix: {st.resolution_summary.slice(0, 80)}...
                        </Typography>
                      )}
                    </Box>
                  ))}
                </Box>
              </Paper>
            )}

            <Grid container spacing={3}>
              <Grid item xs={12} md={7}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                  DESCRIPTION & CONTEXT:
                </Typography>
                <Paper sx={{ p: 2, bgcolor: theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A', marginTop: 1, marginBottom: 2 }}>
                  <Typography variant="body2">{ticketDetail.description}</Typography>
                </Paper>

                {/* ITSM TIMELINE & AUDIT LOGS */}
                <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700, display: 'block', marginBottom: 8 }}>
                  ITSM PUBLIC REPLY & INTERNAL NOTES TIMELINE:
                </Typography>

                <Box maxHeight={220} overflow="auto" mb={2.5}>
                  <ITSMTimeline comments={ticketDetail.comments || []} />
                </Box>

                {/* COMMENT INPUT FORM */}
                <Box display="flex" flexDirection="column" gap={1}>
                  <TextField
                    fullWidth
                    multiline
                    rows={2}
                    placeholder="Add public reply to employee or 🔒 internal note..."
                    value={commentText}
                    onChange={(e) => setCommentText(e.target.value)}
                  />
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Button variant={isInternal ? 'contained' : 'outlined'} color="warning" size="small" onClick={() => setIsInternal(!isInternal)}>
                      {isInternal ? '🔒 Internal Note Mode' : 'Public Reply Mode'}
                    </Button>
                    <Button
                      variant="contained"
                      size="small"
                      disabled={submittingComment || !commentText.trim()}
                      style={{ backgroundColor: '#2563EB' }}
                      onClick={handleAddComment}
                    >
                      {submittingComment ? 'Posting...' : 'Post Comment'}
                    </Button>
                  </Box>
                </Box>
              </Grid>

              {/* Right Column: Resolve Action or Resolution Summary */}
              <Grid item xs={12} md={5}>
                {ticketDetail.status === 'resolved' || ticketDetail.status === 'closed' || showResolveForm ? (
                  <Paper sx={{ p: 2.5, bgcolor: 'background.paper', border: '1.5px solid #10B981', borderRadius: 2 }}>
                    <Typography variant="subtitle2" fontWeight={800} style={{ color: '#10B981', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <CheckCircleIcon />
                      {ticketDetail.status === 'resolved' || ticketDetail.status === 'closed' ? 'Resolution Record & Root Cause' : 'Close Action (Resolves for ALL Linked Requesters)'}
                    </Typography>

                    <Typography variant="caption" style={{ color: theme.palette.text.secondary, display: 'block', marginBottom: 12 }}>
                      Resolves for all {ticketDetail.requester_count} linked requesters ({ticketDetail.linked_requesters?.map((r: any) => r.name).join(', ')}).
                    </Typography>

                    <TextField
                      select
                      label="Root Cause Category"
                      fullWidth
                      size="small"
                      disabled={isClosed}
                      value={rootCause}
                      onChange={(e) => setRootCause(e.target.value)}
                      sx={{ mb: 1.5 }}
                      SelectProps={{ native: true }}
                    >
                      <option value="Hardware Defect">Hardware Defect</option>
                      <option value="Software Bug">Software Bug</option>
                      <option value="Network Degradation">Network Degradation</option>
                      <option value="User Error">User Error / Credentials</option>
                      <option value="Permission Issue">Permission Issue</option>
                    </TextField>

                    <TextField
                      fullWidth
                      multiline
                      rows={3}
                      label="Resolution Summary (User-facing)"
                      disabled={isClosed}
                      value={resolutionSummary}
                      onChange={(e) => setResolutionSummary(e.target.value)}
                      placeholder="Plain-language description visible to end users..."
                      sx={{ mb: 1.5 }}
                    />

                    <TextField
                      fullWidth
                      multiline
                      rows={3}
                      label="Technical Details & Audit Steps"
                      disabled={isClosed}
                      value={resolutionDetail}
                      onChange={(e) => setResolutionDetail(e.target.value)}
                      placeholder="Internal technical details, changed configs, T-codes, PR links..."
                      sx={{ mb: 1.5 }}
                    />

                    {!isClosed && (
                      <Button
                        variant="contained"
                        color="success"
                        fullWidth
                        disabled={submittingResolve || !resolutionSummary.trim()}
                        style={{ fontWeight: 700 }}
                        onClick={handleResolve}
                      >
                        {submittingResolve ? 'Resolving...' : 'Confirm Resolution & Resolve'}
                      </Button>
                    )}
                  </Paper>
                ) : (
                  <Paper sx={{ p: 3, textAlign: 'center', bgcolor: theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A', border: `1px dashed ${theme.palette.divider}`, borderRadius: 2 }}>
                    <Typography variant="subtitle2" fontWeight={700} mb={1}>
                      Ticket is currently OPEN / IN PROGRESS
                    </Typography>
                    <Typography variant="caption" style={{ color: theme.palette.text.secondary, display: 'block', mb: 2.5 }}>
                      Work with the employee via public replies or internal notes. When ready, click below to open the resolution form.
                    </Typography>
                    <Button
                      variant="contained"
                      color="success"
                      size="large"
                      fullWidth
                      startIcon={<CheckCircleIcon />}
                      style={{ fontWeight: 800, padding: '10px 16px' }}
                      onClick={() => {
                        setShowResolveForm(true)
                        setCurrentStatus('resolved')
                      }}
                    >
                      Resolve Ticket
                    </Button>
                  </Paper>
                )}
              </Grid>
            </Grid>
          </DialogContent>
          <DialogActions style={{ padding: '16px 24px' }}>
            <Button onClick={() => setDetailOpen(false)} variant="outlined">
              Close Workspace
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Box>
  )
}
