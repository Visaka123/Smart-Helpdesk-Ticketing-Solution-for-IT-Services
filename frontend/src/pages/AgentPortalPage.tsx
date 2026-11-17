import React, { useState, useEffect, useMemo } from 'react'
import { useOutletContext } from 'react-router-dom'
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
import BeachAccessIcon from '@mui/icons-material/BeachAccess'
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import HistoryEduIcon from '@mui/icons-material/HistoryEdu'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import DownloadIcon from '@mui/icons-material/Download'
import DescriptionIcon from '@mui/icons-material/Description'
import axios from 'axios'
import { fixesApi, availabilityApi } from '../api/services'
import type { SuggestedFix, AgentAvailability } from '../types'
import { STATUS_OPTIONS, normalizeStatus, getStatusOptions } from '../utils/status'
import { AvailabilityDot, getAvailStatus } from '../components/ui/AvailabilityBadge'

import { PriorityBadge, SLABadge, StatusBadge } from '../components/ui/SemanticBadges'
import { ITSMTimeline } from '../components/ui/ITSMTimeline'
import { KnowledgeRecommendationPanel } from '../components/ui/KnowledgeRecommendationPanel'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

const DEFAULT_TEAM_OPTIONS = [
  'Unassigned/Triage',
  'Network Operations',
  'Network Team',
  'Network & Security',
  'Application Support',
  'Database Operations',
  'DevOps & Cloud Infra',
  'SAP / ERP Team',
  'Identity & Access Management',
  'IT Admin',
  'Desktop Support',
  'Procurement',
  'HR Operations',
  'General Support',
]

function getTeamOptions(current?: string) {
  if (current && !DEFAULT_TEAM_OPTIONS.includes(current)) {
    return [current, ...DEFAULT_TEAM_OPTIONS]
  }
  return DEFAULT_TEAM_OPTIONS
}

export default function AgentPortalPage() {
  const theme = useTheme()
  const context = useOutletContext<{ currentRole?: string; viewingAsAgent?: string | null }>()
  const currentRole = context?.currentRole || 'agent'
  const viewingAsAgent = context?.viewingAsAgent || localStorage.getItem('viewing_as_agent')
  const [tabValue, setTabValue] = useState(0)
  const [tickets, setTickets] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [managerData, setManagerData] = useState<any>(null)
  const [myStatus, setMyStatus] = useState<any>(null)

  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null)
  const [ticketDetail, setTicketDetail] = useState<any>(null)
  const [recommendations, setRecommendations] = useState<any[]>([])
  const [loadingRecommendations, setLoadingRecommendations] = useState(false)
  const [workedFixes, setWorkedFixes] = useState<SuggestedFix[]>([])
  const [loadingWorkedFixes, setLoadingWorkedFixes] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)

  // Agent Workspace UI state
  const [showResolveForm, setShowResolveForm] = useState(false)
  const [rosterAgents, setRosterAgents] = useState<AgentAvailability[]>([])
  const [reassignDialogOpen, setReassignDialogOpen] = useState(false)
  const [pendingEngineer, setPendingEngineer] = useState('')
  const [reassignReason, setReassignReason] = useState('')
  const [submittingReassign, setSubmittingReassign] = useState(false)

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

  const getAuthHeaders = () => {
    const token = localStorage.getItem('token')
    const storedUser = localStorage.getItem('user')
    const currentViewingAs = viewingAsAgent || localStorage.getItem('viewing_as_agent')
    const isDemo = localStorage.getItem('demo_mode') === 'true'
    const headers: any = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    if (currentViewingAs) {
      headers['X-View-As-Agent'] = currentViewingAs
      headers['X-Real-User-Role'] = 'manager'
    }
    if (isDemo) {
      headers['X-Demo-Mode'] = 'true'
    }
    if (storedUser) {
      try {
        const u = JSON.parse(storedUser)
        headers['X-User-Id'] = String(u.id)
        headers['X-User-Role'] = u.role || 'agent'
        headers['X-User-Email'] = u.email
        headers['X-User-Name'] = u.name
      } catch (e) {}
    } else {
      headers['X-User-Role'] = 'agent'
    }
    return headers
  }

  const fetchRosterAgents = async () => {
    try {
      const res = await availabilityApi.getAvailableNow()
      if (Array.isArray(res.data)) {
        setRosterAgents(res.data)
      }
    } catch (e) {
      console.error('Error fetching available agents:', e)
    }
  }

  const fetchAgentQueue = async () => {
    try {
      const headers = getAuthHeaders()

      const [qRes, sRes, mRes, statusRes] = await Promise.all([
        axios.get(`${API_BASE}/agent/queue`, { headers }),
        axios.get(`${API_BASE}/agent/agent-stats`, { headers }),
        axios.get(`${API_BASE}/agent/manager-dashboard`, { headers }),
        axios.get(`${API_BASE}/agent/my-status`, { headers }).catch(() => ({ data: null })),
      ])
      setTickets(Array.isArray(qRes.data) ? qRes.data : [])
      setStats(sRes.data)
      setManagerData(mRes.data)
      if (statusRes?.data) setMyStatus(statusRes.data)
    } catch (e) {
      console.error('Error fetching agent queue:', e)
      setTickets([])
    }
  }

  useEffect(() => {
    fetchAgentQueue()
    fetchRosterAgents()
    const handleRefresh = () => {
      fetchAgentQueue()
      fetchRosterAgents()
    }
    window.addEventListener('view_as_changed', handleRefresh)
    window.addEventListener('storage', handleRefresh)
    window.addEventListener('demo_mode_changed', handleRefresh)
    return () => {
      window.removeEventListener('view_as_changed', handleRefresh)
      window.removeEventListener('storage', handleRefresh)
      window.removeEventListener('demo_mode_changed', handleRefresh)
    }
  }, [viewingAsAgent, currentRole])

  const openTicketDetail = (id: number) => {
    setSelectedTicketId(id)
    setShowResolveForm(false)
    setRecommendations([])
    setWorkedFixes([])
    setLoadingWorkedFixes(true)
    fetchRosterAgents()

    // 1. INSTANT MODAL OPEN (0ms blocking delay) using queue ticket data if available
    const existingInQueue = tickets.find((t) => t.id === id)
    if (existingInQueue) {
      setTicketDetail(existingInQueue)
      setCurrentPriority(existingInQueue.priority || 'Medium')
      setCurrentStatus(normalizeStatus(existingInQueue.status || 'open'))
      setCurrentTeam(existingInQueue.assigned_team || 'Unassigned/Triage')
      setAssignedEngineer(existingInQueue.assigned_agent_name || 'Sarah Agent')
      setResolutionSummary(existingInQueue.resolution_summary || '')
      setResolutionDetail(existingInQueue.resolution_detail || '')
      setRootCause(existingInQueue.root_cause || 'User Error')
      if (normalizeStatus(existingInQueue.status) === 'resolved' || normalizeStatus(existingInQueue.status) === 'closed') {
        setShowResolveForm(true)
      }
      fixesApi
        .suggestFixes(existingInQueue.title, existingInQueue.description, existingInQueue.category)
        .then((fRes) => setWorkedFixes(Array.isArray(fRes.data) ? fRes.data : []))
        .catch(() => setWorkedFixes([]))
        .finally(() => setLoadingWorkedFixes(false))
    }
    setDetailOpen(true) // Open modal shell IMMEDIATELY!

    // 2. NON-BLOCKING ASYNC BACKGROUND DATA FETCHING
    const headers = getAuthHeaders()

    axios
      .get(`${API_BASE}/agent/detail/${id}`, { headers })
      .then((res) => {
        setTicketDetail(res.data)
        setCurrentPriority(res.data.priority || 'Medium')
        setCurrentStatus(normalizeStatus(res.data.status || 'open'))
        setCurrentTeam(res.data.assigned_team || 'Unassigned/Triage')
        setAssignedEngineer(res.data.assigned_agent_name || 'Sarah Agent')
        setResolutionSummary(res.data.resolution_summary || '')
        setResolutionDetail(res.data.resolution_detail || '')
        setRootCause(res.data.root_cause || 'User Error')
        if (normalizeStatus(res.data.status) === 'resolved' || normalizeStatus(res.data.status) === 'closed') {
          setShowResolveForm(true)
        }

        fixesApi
          .suggestFixes(res.data.title, res.data.description, res.data.category)
          .then((fRes) => setWorkedFixes(Array.isArray(fRes.data) ? fRes.data : []))
          .catch(() => setWorkedFixes([]))
          .finally(() => setLoadingWorkedFixes(false))

        // Stream recommendations asynchronously in background
        setLoadingRecommendations(true)
        axios
          .post(`${API_BASE}/chatbot/recommendations`, {
            title: res.data.title,
            description: res.data.description,
          })
          .then((recRes) => {
            setRecommendations(recRes.data.recommended_articles || [])
          })
          .catch((err) => {
            console.error('Error fetching recommendations:', err)
            setRecommendations([])
          })
          .finally(() => {
            setLoadingRecommendations(false)
          })
      })
      .catch((e) => {
        console.error('Error loading ticket detail:', e)
      })
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
    if (!selectedTicketId || submittingAction) return
    const norm = normalizeStatus(newStatus)
    if (norm === normalizeStatus(currentStatus)) return

    if (norm === 'resolved') {
      setShowResolveForm(true)
      return
    }

    setCurrentStatus(norm)
    if (norm === 'closed') {
      setShowResolveForm(true)
    }

    try {
      setSubmittingAction(true)
      const headers = getAuthHeaders()
      await axios.post(`${API_BASE}/agent/change-status/${selectedTicketId}`, { new_status: norm }, { headers })
      setTicketDetail((prev: any) => (prev ? { ...prev, status: norm } : prev))
      openTicketDetail(selectedTicketId)
      fetchAgentQueue()
    } catch (e) {
      console.error(e)
    } finally {
      setSubmittingAction(false)
    }
  }

  const handleConfirmReassign = async () => {
    if (!selectedTicketId || !pendingEngineer || !reassignReason.trim() || submittingReassign) return
    try {
      setSubmittingReassign(true)
      const headers = getAuthHeaders()
      await axios.post(
        `${API_BASE}/agent/assign-engineer/${selectedTicketId}`,
        { agent_name: pendingEngineer, reason: reassignReason.trim() },
        { headers }
      )
      setAssignedEngineer(pendingEngineer)
      setTicketDetail((prev: any) => (prev ? { ...prev, assigned_agent_name: pendingEngineer } : prev))
      setReassignDialogOpen(false)
      setPendingEngineer('')
      setReassignReason('')
      openTicketDetail(selectedTicketId)
      fetchAgentQueue()
    } catch (e: any) {
      console.error(e)
      alert(e?.response?.data?.detail || 'Failed to reassign engineer.')
    } finally {
      setSubmittingReassign(false)
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

  const storedUserRaw = localStorage.getItem('user')
  let parsedRole = currentRole
  try {
    if (storedUserRaw) {
      const u = JSON.parse(storedUserRaw)
      if (u.role) parsedRole = u.role
    }
  } catch {}
  const isManager = ['manager', 'admin', 'team_lead'].includes(currentRole || '') || ['manager', 'admin', 'team_lead'].includes(parsedRole || '')
  const isClosed = normalizeStatus(currentStatus) === 'closed' || (ticketDetail && normalizeStatus(ticketDetail.status) === 'closed')

  const engineerOptions = useMemo(() => {
    const list = [...rosterAgents]
    const curName = assignedEngineer || ticketDetail?.assigned_agent_name
    if (curName && !list.some((a) => (a.name || (a as any).agent_name) === curName)) {
      list.unshift({
        id: -1,
        name: curName,
        agent_name: curName,
        team: ticketDetail?.assigned_team || 'General Support',
        timezone: 'Asia/Kolkata',
        skills: '',
        shift_end: null,
        available: true,
        on_shift: true,
        on_call: false,
        on_leave: false,
        below_cap: true,
        open_tickets: 0,
        ticket_cap: 10,
      } as any)
    }
    return list
  }, [rosterAgents, assignedEngineer, ticketDetail?.assigned_agent_name, ticketDetail?.assigned_team])

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

      {!viewingAsAgent && currentRole === 'manager' && (
        <Box borderBottom={1} borderColor="divider" mb={3}>
          <Tabs value={tabValue} onChange={(_, val) => setTabValue(val)} indicatorColor="primary" textColor="primary">
            <Tab label="Agent Ticket Queue" style={{ fontWeight: 700 }} />
            <Tab label="Manager SLA Escalation Center" style={{ fontWeight: 700 }} />
          </Tabs>
        </Box>
      )}

      {(viewingAsAgent || currentRole === 'agent' || tabValue === 0) ? (
        <Box>
          {myStatus?.is_on_leave && (
            <Alert
              severity="warning"
              sx={{
                mb: 3,
                fontWeight: 700,
                fontSize: '1rem',
                border: '1px solid #F59E0B',
                bgcolor: theme.palette.mode === 'light' ? '#FEF3C7' : '#78350F',
                color: theme.palette.mode === 'light' ? '#92400E' : '#FDE68A',
              }}
            >
              You are on leave until {myStatus.leave_until || 'further notice'}
            </Alert>
          )}
          <Grid container spacing={2} mb={3}>
            <Grid item xs={12} sm={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                  OPEN TICKETS / CAP
                </Typography>
                <Typography variant="h4" fontWeight={800} style={{ color: '#2563EB', marginTop: 4 }}>
                  {myStatus ? `${myStatus.open_tickets} / ${myStatus.ticket_cap}` : `${tickets.length} / 10`}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                  SHIFT STATUS
                </Typography>
                {myStatus?.is_on_leave || myStatus?.shift_status === 'On Leave' ? (
                  <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                    <BeachAccessIcon style={{ color: '#D97706', fontSize: 24 }} />
                    <Typography variant="h4" fontWeight={800} style={{ color: '#D97706' }}>
                      On Leave
                    </Typography>
                  </Box>
                ) : (
                  <Typography variant="h4" fontWeight={800} style={{ color: myStatus?.shift_status === 'In Shift' ? '#10B981' : '#D97706', marginTop: 4 }}>
                    {myStatus?.shift_status || 'In Shift'}
                  </Typography>
                )}
              </Paper>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                  SHIFT TIMING
                </Typography>
                <Typography variant="h6" fontWeight={800} style={{ color: theme.palette.text.primary, marginTop: 8 }}>
                  {myStatus?.next_shift || 'Shift ends 18:00 IST'}
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                  RESOLVED TICKETS
                </Typography>
                <Typography variant="h4" fontWeight={800} style={{ color: '#10B981', marginTop: 4 }}>
                  {stats?.tickets_resolved || 0}
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
                {tickets.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} align="center" sx={{ py: 6 }}>
                      <Typography variant="body1" fontWeight={600} style={{ color: theme.palette.text.secondary }}>
                        No tickets in your queue.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  tickets.map((t) => (
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
                          value={t.assigned_team || 'General Support'}
                          onChange={(e) => handleInlineAssignTeam(t.id, e.target.value)}
                          sx={{ fontSize: '0.78rem', height: 32, minWidth: 180 }}
                        >
                          {getTeamOptions(t.assigned_team).map((opt) => (
                            <MenuItem key={opt} value={opt}>
                              {opt === 'Unassigned/Triage' ? '⚠️ Unassigned/Triage' : opt}
                            </MenuItem>
                          ))}
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Button variant="contained" size="small" style={{ backgroundColor: '#2563EB' }} onClick={() => openTicketDetail(t.id)}>
                          Open Workspace
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
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
                <StatusBadge status={currentStatus || ticketDetail.status} />
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
                    <Select
                      value={normalizeStatus(currentStatus)}
                      label="Status"
                      onChange={(e) => handleChangeStatus(e.target.value)}
                    >
                      {getStatusOptions(currentStatus).map((opt) => (
                        <MenuItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </MenuItem>
                      ))}
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
                    <Select value={currentTeam || 'General Support'} label="Team Assignment" onChange={(e) => handleInlineAssignTeam(ticketDetail.id, e.target.value)}>
                      {getTeamOptions(currentTeam).map((opt) => (
                        <MenuItem key={opt} value={opt}>
                          {opt === 'Unassigned/Triage' ? '⚠️ Unassigned/Triage' : opt}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                <Grid item xs={12} sm={3}>
                  <FormControl fullWidth size="small" disabled={isClosed || !isManager}>
                    <InputLabel>Assigned Engineer</InputLabel>
                    <Select
                      value={assignedEngineer || ticketDetail?.assigned_agent_name || ''}
                      label="Assigned Engineer"
                      onChange={(e) => {
                        const newName = e.target.value
                        if (newName && newName !== assignedEngineer) {
                          setPendingEngineer(newName)
                          setReassignReason('')
                          setReassignDialogOpen(true)
                        }
                      }}
                    >
                      {engineerOptions.map((agent: any) => {
                        const name = agent.name || agent.agent_name
                        const avail = getAvailStatus(agent)
                        let availLabel = 'Available'
                        if (avail === 'on_leave') availLabel = 'On leave'
                        else if (avail === 'off_shift') availLabel = 'Off shift'
                        else if (avail === 'at_capacity' || avail === 'over_capacity') availLabel = 'At capacity'

                        const isOnLeave = avail === 'on_leave'
                        return (
                          <MenuItem key={name} value={name} disabled={isOnLeave}>
                            <Box display="flex" alignItems="center" gap={1}>
                              <AvailabilityDot status={avail} />
                              <Typography variant="body2" component="span">
                                {name} ({availLabel})
                              </Typography>
                            </Box>
                          </MenuItem>
                        )
                      })}
                    </Select>
                  </FormControl>
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
            {(loadingRecommendations || (recommendations && recommendations.length > 0)) && (
              <KnowledgeRecommendationPanel articles={recommendations} loading={loadingRecommendations} />
            )}

            {/* SUGGESTIONS TRIED BY USER */}
            {ticketDetail.suggestions_tried && (() => {
              let triedList: any[] = []
              try {
                const parsed = typeof ticketDetail.suggestions_tried === 'string' ? JSON.parse(ticketDetail.suggestions_tried) : ticketDetail.suggestions_tried
                triedList = Array.isArray(parsed) ? parsed : [parsed]
              } catch {
                triedList = [{ title: ticketDetail.suggestions_tried }]
              }
              if (triedList.length === 0) return null
              return (
                <Paper sx={{ p: 2, bgcolor: theme.palette.mode === 'light' ? '#FEF2F2' : '#2A1215', border: '1px solid #FECACA', borderRadius: 2, mb: 2 }}>
                  <Typography variant="caption" fontWeight={800} sx={{ color: '#DC2626', display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                    <HistoryEduIcon sx={{ fontSize: 16 }} /> SUGGESTIONS TRIED BY USER (DO NOT REPEAT):
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                    The employee already attempted these self-service solutions before submitting the ticket:
                  </Typography>
                  <Box display="flex" flexDirection="column" gap={0.5}>
                    {triedList.map((item: any, idx: number) => (
                      <Typography key={idx} variant="caption" sx={{ color: '#991B1B', fontWeight: 600 }}>
                        • {item.ticket_id ? `#${item.ticket_id}: ` : ''}{item.title || JSON.stringify(item)}
                      </Typography>
                    ))}
                  </Box>
                </Paper>
              )
            })()}

            {/* FIXES THAT WORKED BEFORE */}
            {workedFixes && workedFixes.length > 0 && (
              <Paper sx={{ p: 2, bgcolor: theme.palette.mode === 'light' ? '#F0FDF4' : '#062012', border: '1px solid #BBF7D0', borderRadius: 2, mb: 2.5 }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                  <Typography variant="caption" fontWeight={800} sx={{ color: '#15803D', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <LightbulbOutlinedIcon sx={{ fontSize: 16 }} /> FIXES THAT WORKED BEFORE:
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {workedFixes.length} similar resolved incidents
                  </Typography>
                </Box>
                <Box display="flex" flexDirection="column" gap={1.5}>
                  {workedFixes.map((st) => {
                    const validPct = Math.round(st.relevance * 100)
                    return (
                      <Box key={st.ticket_id} sx={{ p: 1.5, bgcolor: 'background.paper', borderRadius: 1.5, border: `1px solid ${theme.palette.divider}` }}>
                        <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
                          <Typography variant="body2" fontWeight={700} sx={{ color: theme.palette.text.primary }}>
                            #{st.ticket_id} - {st.title}
                          </Typography>
                          <Chip label={`${validPct}% Match`} size="small" sx={{ height: 20, fontSize: '0.7rem', fontWeight: 700, bgcolor: '#DCFCE7', color: '#15803D' }} />
                        </Box>
                        {st.resolution_summary && (
                          <Typography variant="caption" display="block" sx={{ color: theme.palette.text.secondary, fontStyle: 'italic', mb: 1 }}>
                            Fix: {st.resolution_summary}
                          </Typography>
                        )}
                        <Box display="flex" justifyContent="flex-end">
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<ContentCopyIcon sx={{ fontSize: 14 }} />}
                            onClick={() => {
                              setCommentText(st.resolution_summary)
                              setResolutionSummary(st.resolution_summary)
                            }}
                            sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.25 }}
                          >
                            Use this resolution
                          </Button>
                        </Box>
                      </Box>
                    )
                  })}
                </Box>
              </Paper>
            )}

            {/* SIMILAR RESOLVED TICKETS (LEGACY FALLBACK) */}
            {(!workedFixes || workedFixes.length === 0) && ticketDetail.similar_tickets && ticketDetail.similar_tickets.length > 0 && (
              <Paper sx={{ p: 2, bgcolor: theme.palette.mode === 'light' ? '#FFFBEB' : '#2A1B14', border: '1px solid #FDE68A', borderRadius: 2, mb: 2.5 }}>
                <Typography variant="caption" fontWeight={800} sx={{ color: '#B45309', display: 'block', mb: 1 }}>
                  SIMILAR RESOLVED INCIDENTS (HYBRID MATCH):
                </Typography>
                <Box display="flex" flexDirection="column" gap={1}>
                  {ticketDetail.similar_tickets.map((st: any) => {
                    const rawScore = st.similarity_score ?? st.relevance_pct ?? st.score
                    const validPct = typeof rawScore === 'number' && !isNaN(rawScore)
                      ? (rawScore <= 1.0 ? Math.round(rawScore * 100) : Math.round(rawScore))
                      : null
                    const matchLabel = validPct != null ? `(Match: ${validPct}%)` : '(Related Incident)'
                    return (
                      <Box key={st.id} display="flex" justifyContent="space-between" alignItems="center">
                        <Typography variant="caption" fontWeight={700} style={{ color: '#92400E' }}>
                          #{st.id} - {st.title} {matchLabel}
                        </Typography>
                        {st.resolution_summary && (
                          <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontStyle: 'italic' }}>
                            Fix: {st.resolution_summary.slice(0, 80)}...
                          </Typography>
                        )}
                      </Box>
                    )
                  })}
                </Box>
              </Paper>
            )}

            <Grid container spacing={3}>
              <Grid item xs={12} md={7}>
                <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                  DESCRIPTION & CONTEXT:
                </Typography>
                <Paper
                  elevation={0}
                  sx={{
                    p: 2.5,
                    bgcolor: theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A',
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: 2,
                    marginTop: 1,
                    marginBottom: 2.5,
                    '& p': { margin: '0 0 12px 0', lineHeight: 1.65, fontSize: '0.9rem' },
                    '& p:last-child': { margin: 0 },
                    '& h3': { marginTop: '16px', marginBottom: '8px', fontSize: '1rem', fontWeight: 800, color: theme.palette.mode === 'light' ? '#0F172A' : '#F8FAFC' },
                    '& ul, & ol': { margin: '0 0 12px 0', paddingLeft: '20px' },
                    '& li': { marginBottom: '6px', lineHeight: 1.6 },
                    '& strong': { color: theme.palette.mode === 'light' ? '#1E3A8A' : '#93C5FD' },
                  }}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {ticketDetail.description ? ticketDetail.description.replace(/\\n/g, '\n') : ''}
                  </ReactMarkdown>
                </Paper>

                {/* ATTACHED DOCUMENTS */}
                {ticketDetail.attachments && ticketDetail.attachments.length > 0 && (
                  <Box mb={2}>
                    <Box display="flex" alignItems="center" gap={1} mb={1}>
                      <AttachFileIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                      <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
                        ATTACHED DOCUMENTS ({ticketDetail.attachments.length}):
                      </Typography>
                    </Box>
                    <Grid container spacing={1}>
                      {ticketDetail.attachments.map((att: any) => (
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
                              bgcolor: theme.palette.mode === 'light' ? '#FFFFFF' : '#1E293B',
                            }}
                          >
                            <Box display="flex" alignItems="center" gap={1} sx={{ minWidth: 0 }}>
                              <DescriptionIcon sx={{ color: '#2563EB', fontSize: 20 }} />
                              <Box sx={{ minWidth: 0 }}>
                                <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: { xs: 140, sm: 190 } }}>
                                  {att.filename}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {att.formatted_size || `${(att.file_size / 1024).toFixed(1)} KB`} • {att.uploaded_by || 'User'}
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
                    <Typography variant="caption" sx={{ color: theme.palette.text.secondary, display: 'block', mb: 2.5 }}>
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

      {/* Manager Reassignment Reason Dialog */}
      <Dialog
        open={reassignDialogOpen}
        onClose={() => !submittingReassign && setReassignDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>Reassign Engineer</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Reassigning Ticket #{selectedTicketId} to <strong>{pendingEngineer}</strong>. A reason is required for assignment history.
          </Typography>
          <TextField
            autoFocus
            label="Reassignment Reason"
            fullWidth
            size="small"
            required
            multiline
            rows={2}
            value={reassignReason}
            onChange={(e) => setReassignReason(e.target.value)}
            placeholder="e.g. Specialized expertise, shift coverage, load rebalancing"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => {
              setReassignDialogOpen(false)
              setPendingEngineer('')
              setReassignReason('')
            }}
            disabled={submittingReassign}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={!reassignReason.trim() || submittingReassign}
            onClick={handleConfirmReassign}
          >
            Confirm Reassign
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
