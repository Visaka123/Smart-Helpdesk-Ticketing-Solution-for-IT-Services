import React, { useEffect, useState } from 'react'
import {
  Box,
  Typography,
  Card,
  CardContent,
  Chip,
  Button,
  Grid,
  ToggleButtonGroup,
  ToggleButton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Paper,
  Tooltip,
  useTheme,
} from '@mui/material'
import ViewCarouselIcon from '@mui/icons-material/ViewCarousel'
import TableChartIcon from '@mui/icons-material/TableChart'
import AddIcon from '@mui/icons-material/Add'
import { useNavigate, useOutletContext } from 'react-router-dom'
import axios from 'axios'

import { PriorityBadge, SLABadge, StatusBadge } from '../components/ui/SemanticBadges'
import EmployeeTicketDetailsModal from '../components/EmployeeTicketDetailsModal'

const API_BASE = 'http://localhost:8000'

interface Ticket {
  id: number
  title: string
  description: string
  category: string
  priority: string
  status: string
  predicted_team: string
  routing_confidence: number
  sla_badge: string
  is_sla_breached: boolean
  requester_name: string
  created_at: string
  sla_due_at: string
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const theme = useTheme()
  const context = useOutletContext<{ currentRole?: string }>()
  const currentRole = context?.currentRole || 'employee'
  const isEmployee = currentRole === 'employee'

  const [viewMode, setViewMode] = useState<'rows' | 'table'>('rows')
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  // Employee details modal state
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null)
  const [employeeModalOpen, setEmployeeModalOpen] = useState(false)

  const fetchDashboardData = async () => {
    try {
      setLoading(true)
      const token = localStorage.getItem('token')
      const storedUser = localStorage.getItem('user')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (storedUser) {
        try {
          const u = JSON.parse(storedUser)
          headers['X-User-Id'] = String(u.id)
          headers['X-User-Role'] = currentRole
          headers['X-User-Email'] = u.email
          headers['X-User-Name'] = u.name
        } catch (e) {}
      } else {
        headers['X-User-Role'] = currentRole
      }

      const [tRes, sRes] = await Promise.all([
        axios.get(`${API_BASE}/ticket/all`, { headers }),
        axios.get(`${API_BASE}/ticket/stats`),
      ])
      setTickets(tRes.data)
      setStats(sRes.data)
    } catch (err) {
      console.error('Error fetching dashboard tickets:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDashboardData()
  }, [currentRole])

  const handleTicketClick = (ticketId: number) => {
    if (isEmployee) {
      setSelectedTicketId(ticketId)
      setEmployeeModalOpen(true)
    } else {
      navigate('/agent-portal')
    }
  }

  const ACTIVE_STATUSES = ['new', 'open', 'assigned', 'in_progress', 'waiting_for_user', 'on_hold']
  const FINAL_STATUSES = ['resolved', 'closed', 'cancelled']

  const userTickets = isEmployee
    ? tickets.filter((t) => {
        const req = (t.requester_name || '').toLowerCase()
        return req.includes('alice') || req.includes('employee') || req === ''
      })
    : tickets

  const activeTickets = userTickets.filter((t) => ACTIVE_STATUSES.includes((t.status || 'open').toLowerCase()))
  const resolvedTickets = userTickets.filter((t) => FINAL_STATUSES.includes((t.status || 'open').toLowerCase()))

  const unassignedTickets = activeTickets.filter((t) => t.predicted_team === 'Unassigned/Triage')
  const breachedOrAtRisk = activeTickets.filter((t) => t.sla_badge === 'BREACHED' || t.sla_badge === 'AT_RISK')

  const renderHorizontalCardRow = (title: string, subtitle: string, items: Ticket[], isWarningRow = false) => (
    <Box mb={4}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
        <Box>
          <Typography variant="h5" fontWeight={800} style={{ color: isWarningRow ? '#DC2626' : theme.palette.text.primary }}>
            {title}
          </Typography>
          <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
            {subtitle}
          </Typography>
        </Box>
        <Typography variant="caption" fontWeight={700} style={{ color: isWarningRow ? '#DC2626' : '#2563EB' }}>
          {items.length} TICKETS
        </Typography>
      </Box>

      {items.length === 0 ? (
        <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'background.paper', border: '1px dashed', borderColor: 'divider' }}>
          <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>
            No tickets in this row.
          </Typography>
        </Paper>
      ) : (
        <Box
          display="flex"
          gap={2}
          overflow="auto"
          py={1}
          sx={{
            '&::-webkit-scrollbar': { height: 6 },
            '&::-webkit-scrollbar-thumb': { backgroundColor: theme.palette.divider, borderRadius: 3 },
          }}
        >
          {items.map((ticket, index) => (
            <Card
              key={ticket.id}
              sx={{
                minWidth: 310,
                maxWidth: 320,
                flexShrink: 0,
                bgcolor: 'background.paper',
                border: isWarningRow ? '1.5px solid #FCA5A5' : `1px solid ${theme.palette.divider}`,
                cursor: 'pointer',
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  transform: 'translateY(-2px)',
                  borderColor: isWarningRow ? '#DC2626' : '#2563EB',
                  boxShadow: '0 6px 16px rgba(0, 0, 0, 0.08)',
                },
              }}
              onClick={() => handleTicketClick(ticket.id)}
            >
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                  <PriorityBadge priority={ticket.priority} />
                  {!isEmployee && <SLABadge badge={ticket.sla_badge} />}
                </Box>

                <Typography variant="h6" fontWeight={700} noWrap title={ticket.title} style={{ color: theme.palette.text.primary, marginBottom: 4 }}>
                  #{isEmployee ? index + 1 : ticket.id} - {ticket.title}
                </Typography>

                <Typography variant="body2" style={{ color: theme.palette.text.secondary, height: 38, overflow: 'hidden' }}>
                  {ticket.description}
                </Typography>

                <Box mt={2} pt={1.5} borderTop={`1px solid ${theme.palette.divider}`} display="flex" justifyContent="space-between" alignItems="center">
                  <Chip
                    label={ticket.category || 'General IT'}
                    size="small"
                    style={{
                      backgroundColor: theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B',
                      color: '#2563EB',
                      fontWeight: 700,
                    }}
                  />
                  <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                    {ticket.created_at ? new Date(ticket.created_at).toLocaleDateString() : ''}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}
    </Box>
  )

  return (
    <Box>
      {/* Header Banners */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h2" fontWeight={800}>
            {isEmployee ? 'Employee Self-Service Portal' : 'Helpdesk Command Center'}
          </Typography>
          <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>
            {isEmployee
              ? 'View your active support requests, track resolution progress, and access help guides'
              : 'Executive Dashboard with Real-time Automated Routing, Priority Engine & SLA Escalation Tracking'}
          </Typography>
        </Box>

        <Box display="flex" gap={2} alignItems="center">
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            style={{ backgroundColor: '#2563EB', fontWeight: 700 }}
            onClick={() => navigate('/tickets/create')}
          >
            Create Ticket
          </Button>

          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(_, val) => val && setViewMode(val)}
            size="small"
            style={{ backgroundColor: theme.palette.background.paper, border: `1px solid ${theme.palette.divider}` }}
          >
            <ToggleButton value="rows" style={{ color: viewMode === 'rows' ? '#2563EB' : theme.palette.text.secondary }}>
              <Tooltip title="Dashboard Cards Row View">
                <ViewCarouselIcon fontSize="small" />
              </Tooltip>
            </ToggleButton>
            <ToggleButton value="table" style={{ color: viewMode === 'table' ? '#2563EB' : theme.palette.text.secondary }}>
              <Tooltip title="Dense Data Table View">
                <TableChartIcon fontSize="small" />
              </Tooltip>
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      {/* KPI Stats Grid */}
      <Grid container spacing={2.5} mb={4}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'background.paper', p: 2 }}>
            <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
              {isEmployee ? 'MY TICKETS' : 'TOTAL TICKETS'}
            </Typography>
            <Typography variant="h3" fontWeight={800} style={{ color: theme.palette.text.primary, marginTop: 4 }}>
              {isEmployee ? tickets.length : (stats?.total_tickets || 0)}
            </Typography>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'background.paper', p: 2, borderLeft: '4px solid #D97706' }}>
            <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
              OPEN / ACTIVE
            </Typography>
            <Typography variant="h3" fontWeight={800} style={{ color: '#D97706', marginTop: 4 }}>
              {activeTickets.length}
            </Typography>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'background.paper', p: 2, borderLeft: '4px solid #10B981' }}>
            <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
              RESOLVED / CLOSED
            </Typography>
            <Typography variant="h3" fontWeight={800} style={{ color: '#10B981', marginTop: 4 }}>
              {resolvedTickets.length}
            </Typography>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'background.paper', p: 2, borderLeft: '4px solid #2563EB' }}>
            <Typography variant="caption" style={{ color: theme.palette.text.secondary, fontWeight: 700 }}>
              {isEmployee ? 'PORTAL STATUS' : 'SLA COMPLIANCE'}
            </Typography>
            <Typography variant="h3" fontWeight={800} style={{ color: '#2563EB', marginTop: 4 }}>
              {isEmployee ? 'ACTIVE' : `${stats?.sla_compliance_pct || 100}%`}
            </Typography>
          </Card>
        </Grid>
      </Grid>

      {/* Main Rows or Table View */}
      {viewMode === 'rows' ? (
        <Box>
          {!isEmployee && unassignedTickets.length > 0 &&
            renderHorizontalCardRow(
              '⚠️ Unassigned / Triage Queue',
              'Tickets requiring manual team assignment by support lead or manager',
              unassignedTickets,
              true
            )}

          {!isEmployee &&
            renderHorizontalCardRow(
              '🚨 Needs Immediate Attention (SLA At Risk & Breached)',
              'Tickets requiring urgent manager or agent intervention before SLA expiration',
              breachedOrAtRisk,
              true
            )}

          {renderHorizontalCardRow(
            isEmployee ? '📋 My Open Support Requests' : '🔥 Active Open Tickets',
            isEmployee ? 'Support requests currently being worked on by IT support specialists' : 'Active support tickets queued for engineering & IT teams',
            activeTickets
          )}

          {renderHorizontalCardRow(
            '✅ Recently Resolved & Closed',
            'Resolved support requests with verified solution summaries',
            resolvedTickets
          )}
        </Box>
      ) : (
        <Paper sx={{ width: '100%', overflow: 'hidden', bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Title</TableCell>
                <TableCell>Priority</TableCell>
                <TableCell>Category</TableCell>
                {!isEmployee && <TableCell>Assigned Team</TableCell>}
                <TableCell>Status</TableCell>
                <TableCell>Created Date</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {tickets.map((t) => (
                <TableRow key={t.id} hover onClick={() => handleTicketClick(t.id)} style={{ cursor: 'pointer' }}>
                  <TableCell style={{ fontWeight: 700, color: '#2563EB' }}>#{t.id}</TableCell>
                  <TableCell style={{ fontWeight: 600, color: theme.palette.text.primary }}>{t.title}</TableCell>
                  <TableCell><PriorityBadge priority={t.priority} /></TableCell>
                  <TableCell>{t.category || 'General IT'}</TableCell>
                  {!isEmployee && (
                    <TableCell>
                      <Chip
                        label={t.predicted_team}
                        size="small"
                        style={{
                          backgroundColor: t.predicted_team === 'Unassigned/Triage' ? '#FEF3C7' : (theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B'),
                          color: t.predicted_team === 'Unassigned/Triage' ? '#D97706' : '#2563EB',
                          fontWeight: 700,
                        }}
                      />
                    </TableCell>
                  )}
                  <TableCell><StatusBadge status={t.status} /></TableCell>
                  <TableCell style={{ color: theme.palette.text.secondary }}>
                    {t.created_at ? new Date(t.created_at).toLocaleDateString() : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}

      {/* Dedicated Employee Ticket Details Modal */}
      <EmployeeTicketDetailsModal
        open={employeeModalOpen}
        ticketId={selectedTicketId}
        onClose={() => setEmployeeModalOpen(false)}
        onRefreshList={fetchDashboardData}
      />
    </Box>
  )
}
