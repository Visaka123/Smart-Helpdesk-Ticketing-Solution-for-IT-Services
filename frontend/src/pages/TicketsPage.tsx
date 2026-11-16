import React, { useEffect, useState, useMemo } from 'react'
import { useNavigate, useOutletContext, useSearchParams, useLocation } from 'react-router-dom'
import {
  Box, Card, CardContent, Typography, TextField, Select, MenuItem,
  FormControl, InputLabel, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TablePagination, TableSortLabel, CircularProgress,
  Button, InputAdornment, Chip, Paper, Alert, useTheme
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import AddIcon from '@mui/icons-material/Add'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import axios from 'axios'

import { PriorityBadge, StatusBadge, SLABadge } from '../components/ui/SemanticBadges'
import EmployeeTicketDetailsModal from '../components/EmployeeTicketDetailsModal'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

type SortField = 'title' | 'status' | 'priority' | 'created_at' | 'predicted_team' | 'assigned_team'
type SortDir = 'asc' | 'desc'

export default function TicketsPage() {
  const navigate = useNavigate()
  const theme = useTheme()
  const context = useOutletContext<{ currentRole?: string }>()
  const currentRole = context?.currentRole || 'employee'
  const [searchParams, setSearchParams] = useSearchParams()
  const location = useLocation()

  const [tickets, setTickets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(10)
  const [sortField, setSortField] = useState<SortField>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  // Employee Modal state
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null)
  const [employeeModalOpen, setEmployeeModalOpen] = useState(false)

  useEffect(() => {
    const openParam = searchParams.get('open') || searchParams.get('id')
    const stateTicketId = (location.state as any)?.openTicketId
    const targetTicketId = openParam ? parseInt(openParam, 10) : (typeof stateTicketId === 'number' ? stateTicketId : (stateTicketId ? parseInt(stateTicketId, 10) : null))

    if (targetTicketId && !isNaN(targetTicketId)) {
      setSelectedTicketId(targetTicketId)
      setEmployeeModalOpen(true)
    }
  }, [searchParams, location.state])

  const handleModalClose = () => {
    setEmployeeModalOpen(false)
    setSelectedTicketId(null)
    if (searchParams.has('open') || searchParams.has('id')) {
      const newParams = new URLSearchParams(searchParams)
      newParams.delete('open')
      newParams.delete('id')
      setSearchParams(newParams, { replace: true })
    }
  }

  const fetchTickets = async () => {
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

      const res = await axios.get(`${API_BASE}/ticket/all`, { headers })
      setTickets(Array.isArray(res.data) ? res.data : [])
    } catch (e) {
      console.error('Error fetching tickets:', e)
      setTickets([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTickets()
  }, [currentRole])

  const handleSort = (field: SortField) => {
    if (sortField === field) setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    else { setSortField(field); setSortDir('asc') }
  }

  const filtered = useMemo(() => {
    let data = [...tickets]
    if (search) {
      const q = search.toLowerCase()
      data = data.filter((t) => t.title?.toLowerCase().includes(q) || t.description?.toLowerCase().includes(q))
    }
    if (statusFilter !== 'all') data = data.filter((t) => t.status?.toLowerCase() === statusFilter)
    if (priorityFilter !== 'all') {
      data = data.filter((t) => (t.priority || '').toLowerCase() === priorityFilter)
    }
    data.sort((a, b) => {
      const av = (a[sortField] || '') as string
      const bv = (b[sortField] || '') as string
      return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
    })
    return data
  }, [tickets, search, statusFilter, priorityFilter, sortField, sortDir])

  const paginated = filtered.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)

  const handleRowClick = (ticketId: number) => {
    if (currentRole === 'employee') {
      setSelectedTicketId(ticketId)
      setEmployeeModalOpen(true)
    } else {
      navigate(`/tickets/${ticketId}`)
    }
  }

  const SortCell = ({ field, label }: { field: SortField; label: string }) => (
    <TableCell style={{ fontWeight: 700 }}>
      <TableSortLabel
        active={sortField === field}
        direction={sortField === field ? sortDir : 'asc'}
        onClick={() => handleSort(field)}
      >
        {label}
      </TableSortLabel>
    </TableCell>
  )

  const isEmployee = currentRole === 'employee'

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h2" fontWeight={800}>
            {isEmployee ? 'My Support Tickets' : 'All Support Tickets'}
          </Typography>
          <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>
            {filtered.length} ticket{filtered.length !== 1 ? 's' : ''} registered {isEmployee ? 'in your portal' : 'across teams'}
          </Typography>
        </Box>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          style={{ backgroundColor: '#2563EB', fontWeight: 700 }}
          onClick={() => navigate('/tickets/create')}
        >
          Raise Ticket
        </Button>
      </Box>

      <Card sx={{ bgcolor: 'background.paper', border: `1px solid ${theme.palette.divider}` }}>
        <CardContent>
          <Box display="flex" gap={2} mb={2.5} flexWrap="wrap">
            <TextField
              placeholder="Search title or description..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0) }}
              sx={{ minWidth: 280 }}
              InputProps={{
                startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" style={{ color: theme.palette.text.secondary }} /></InputAdornment>,
              }}
            />
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Status</InputLabel>
              <Select value={statusFilter} label="Status" onChange={(e) => { setStatusFilter(e.target.value); setPage(0) }}>
                <MenuItem value="all">All Statuses</MenuItem>
                <MenuItem value="open">Open</MenuItem>
                <MenuItem value="in_progress">In Progress</MenuItem>
                <MenuItem value="resolved">Resolved</MenuItem>
                <MenuItem value="closed">Closed</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Priority</InputLabel>
              <Select value={priorityFilter} label="Priority" onChange={(e) => { setPriorityFilter(e.target.value); setPage(0) }}>
                <MenuItem value="all">All Priorities</MenuItem>
                <MenuItem value="critical">Critical</MenuItem>
                <MenuItem value="high">High</MenuItem>
                <MenuItem value="medium">Medium</MenuItem>
                <MenuItem value="low">Low</MenuItem>
              </Select>
            </FormControl>
          </Box>

          {loading ? (
            <Box display="flex" justifyContent="center" py={6}><CircularProgress size={24} style={{ color: '#2563EB' }} /></Box>
          ) : (
            <>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell width={60}>ID</TableCell>
                      <SortCell field="title" label="Title & Description" />
                      <TableCell>Category</TableCell>
                      <SortCell field="status" label="Status" />
                      <SortCell field="priority" label="Priority" />
                      {!isEmployee && <TableCell>SLA Badge</TableCell>}
                      {!isEmployee && <SortCell field="assigned_team" label="ASSIGNED TEAM" />}
                      <SortCell field="created_at" label="Created Date" />
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {paginated.map((t, index) => {
                      const displayId = isEmployee ? `#${page * rowsPerPage + index + 1}` : `#${t.id}`
                      return (
                        <TableRow key={t.id} hover onClick={() => handleRowClick(t.id)} style={{ cursor: 'pointer' }}>
                          <TableCell style={{ fontWeight: 700, color: '#2563EB' }}>
                            {displayId}
                          </TableCell>
                        <TableCell>
                          <Box display="flex" alignItems="center" gap={1}>
                            <Typography variant="body2" fontWeight={600} style={{ color: theme.palette.text.primary }} noWrap sx={{ maxWidth: 300 }}>
                              {t.title}
                            </Typography>
                          </Box>
                          <Typography variant="caption" style={{ color: theme.palette.text.secondary }} noWrap sx={{ maxWidth: 340, display: 'block' }}>
                            {t.description}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip label={t.category || 'General IT'} size="small" style={{ fontSize: '0.72rem', height: 20 }} />
                        </TableCell>
                        <TableCell><StatusBadge status={t.status} /></TableCell>
                        <TableCell><PriorityBadge priority={t.priority} /></TableCell>
                        {!isEmployee && <TableCell><SLABadge badge={t.sla_badge} /></TableCell>}
                        {!isEmployee && (
                          <TableCell>
                            <Chip label={t.assigned_team || t.predicted_team || 'Triage'} size="small" style={{ backgroundColor: theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B', color: '#2563EB', fontWeight: 600 }} />
                          </TableCell>
                        )}
                        <TableCell style={{ color: theme.palette.text.secondary }}>
                          {t.created_at ? new Date(t.created_at).toLocaleDateString() : '—'}
                        </TableCell>
                      </TableRow>
                    )})}
                    {paginated.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={isEmployee ? 6 : 8} align="center">
                          <Typography variant="body2" style={{ color: theme.palette.text.secondary, padding: '24px 0' }}>
                            No tickets match the current filters
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
              <TablePagination
                component="div"
                count={filtered.length}
                page={page}
                onPageChange={(_, p) => setPage(p)}
                rowsPerPage={rowsPerPage}
                onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value)); setPage(0) }}
                rowsPerPageOptions={[5, 10, 25, 50]}
              />
            </>
          )}
        </CardContent>
      </Card>

      {/* Employee Ticket Details Modal */}
      <EmployeeTicketDetailsModal
        open={employeeModalOpen}
        ticketId={selectedTicketId}
        onClose={handleModalClose}
        onRefreshList={fetchTickets}
      />
    </Box>
  )
}
