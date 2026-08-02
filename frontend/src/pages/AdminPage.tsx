import { useEffect, useState, useMemo } from 'react'
import {
  Box, Card, CardContent, Typography, TextField, Select, MenuItem,
  FormControl, InputLabel, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TablePagination, TableSortLabel, CircularProgress,
  Grid, Chip, InputAdornment, Tabs, Tab, Divider,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import { useAppDispatch, useAppSelector } from '../hooks/redux'
import { fetchTickets, fetchStats } from '../store/slices/ticketSlice'
import { StatusBadge, PriorityBadge } from '../components/ui/Badges'
import StatCard from '../components/ui/StatCard'
import PageHeader from '../components/ui/PageHeader'
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import GroupsIcon from '@mui/icons-material/Groups'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import type { Ticket } from '../types'

type SortField = keyof Ticket
type SortDir = 'asc' | 'desc'

export default function AdminPage() {
  const dispatch = useAppDispatch()
  const { tickets, stats, loading } = useAppSelector((s) => s.tickets)

  const [tab, setTab] = useState(0)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [teamFilter, setTeamFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(15)
  const [sortField, setSortField] = useState<string>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  useEffect(() => {
    dispatch(fetchTickets())
    dispatch(fetchStats())
  }, [])

  const teams = useMemo(() => {
    const t = new Set(tickets.map((tk) => tk.predicted_team).filter(Boolean))
    return Array.from(t) as string[]
  }, [tickets])

  const handleSort = (field: string) => {
    if (sortField === field) setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    else { setSortField(field); setSortDir('asc') }
  }

  const filtered = useMemo(() => {
    let data = [...tickets]
    if (search) {
      const q = search.toLowerCase()
      data = data.filter((t) =>
        t.title?.toLowerCase().includes(q) ||
        t.description?.toLowerCase().includes(q) ||
        t.predicted_team?.toLowerCase().includes(q)
      )
    }
    if (statusFilter !== 'all') data = data.filter((t) => t.status?.toLowerCase() === statusFilter)
    if (teamFilter !== 'all') data = data.filter((t) => t.predicted_team === teamFilter)
    data.sort((a: any, b: any) => {
      const av = a[sortField] || ''
      const bv = b[sortField] || ''
      return sortDir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av))
    })
    return data
  }, [tickets, search, statusFilter, teamFilter, sortField, sortDir])

  const paginated = filtered.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)

  const SortCell = ({ field, label, width }: { field: string; label: string; width?: number }) => (
    <TableCell width={width}>
      <TableSortLabel
        active={sortField === field}
        direction={sortField === field ? sortDir : 'asc'}
        onClick={() => handleSort(field)}
      >
        {label}
      </TableSortLabel>
    </TableCell>
  )

  const aiRoutedCount = tickets.filter((t) => t.ai_routed).length
  const kbMatchCount = tickets.filter((t) => t.kb_match).length

  return (
    <Box>
      <PageHeader title="Admin Panel" subtitle="System administration and oversight" />

      <Grid container spacing={2} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="Total Tickets" value={stats?.total_tickets ?? tickets.length} icon={ConfirmationNumberIcon} color="#1E3A8A" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="AI Routed" value={aiRoutedCount} icon={SmartToyIcon} color="#2563EB" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="Active Teams" value={teams.length} icon={GroupsIcon} color="#0284C7" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="KB Matches" value={kbMatchCount} icon={MenuBookIcon} color="#16A34A" />
        </Grid>
      </Grid>

      <Card>
        <Box sx={{ borderBottom: '1px solid #E2E8F0' }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ px: 2 }}>
            <Tab label="All Tickets" />
            <Tab label="AI Routing Results" />
            <Tab label="Team Allocations" />
          </Tabs>
        </Box>

        <CardContent>
          <Box display="flex" gap={2} mb={2.5} flexWrap="wrap">
            <TextField
              placeholder="Search tickets..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(0) }}
              sx={{ minWidth: 260 }}
              InputProps={{
                startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" sx={{ color: '#94A3B8' }} /></InputAdornment>,
              }}
            />
            <FormControl size="small" sx={{ minWidth: 140 }}>
              <InputLabel>Status</InputLabel>
              <Select value={statusFilter} label="Status" onChange={(e) => { setStatusFilter(e.target.value); setPage(0) }}>
                <MenuItem value="all">All Statuses</MenuItem>
                <MenuItem value="open">Open</MenuItem>
                <MenuItem value="closed">Closed</MenuItem>
                <MenuItem value="pending">Pending</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel>Team</InputLabel>
              <Select value={teamFilter} label="Team" onChange={(e) => { setTeamFilter(e.target.value); setPage(0) }}>
                <MenuItem value="all">All Teams</MenuItem>
                {teams.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
              </Select>
            </FormControl>
            <Box ml="auto" display="flex" alignItems="center">
              <Typography variant="body2" color="text.secondary">
                {filtered.length} record{filtered.length !== 1 ? 's' : ''}
              </Typography>
            </Box>
          </Box>

          {loading ? (
            <Box display="flex" justifyContent="center" py={6}><CircularProgress /></Box>
          ) : (
            <>
              {tab === 0 && (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell width={50}>ID</TableCell>
                        <SortCell field="title" label="Title" />
                        <SortCell field="status" label="Status" />
                        <SortCell field="priority" label="Priority" />
                        <SortCell field="predicted_team" label="Team" />
                        <TableCell>AI Routed</TableCell>
                        <TableCell>KB Match</TableCell>
                        <SortCell field="created_at" label="Created" />
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {paginated.map((t) => (
                        <TableRow key={t.id} hover>
                          <TableCell>
                            <Typography variant="caption" color="text.secondary" fontFamily="monospace">
                              {String(t.id).slice(0, 8)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight={500} noWrap sx={{ maxWidth: 280 }}>{t.title}</Typography>
                          </TableCell>
                          <TableCell><StatusBadge status={t.status} /></TableCell>
                          <TableCell><PriorityBadge priority={t.priority || t.predicted_priority} /></TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">{t.predicted_team || '—'}</Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={t.ai_routed ? 'Yes' : 'No'} size="small" color={t.ai_routed ? 'primary' : 'default'} variant="outlined" />
                          </TableCell>
                          <TableCell>
                            <Chip label={t.kb_match ? 'Yes' : 'No'} size="small" color={t.kb_match ? 'success' : 'default'} variant="outlined" />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">
                              {t.created_at ? new Date(t.created_at).toLocaleDateString() : '—'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                      {paginated.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={8} align="center">
                            <Typography variant="body2" color="text.secondary" py={3}>No records found</Typography>
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              {tab === 1 && (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Title</TableCell>
                        <TableCell>Predicted Team</TableCell>
                        <TableCell>Predicted Priority</TableCell>
                        <TableCell>AI Routed</TableCell>
                        <TableCell>KB Match</TableCell>
                        <TableCell>Status</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {paginated.map((t) => (
                        <TableRow key={t.id} hover>
                          <TableCell>
                            <Typography variant="body2" fontWeight={500} noWrap sx={{ maxWidth: 300 }}>{t.title}</Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={t.predicted_team || 'Unassigned'} size="small" variant="outlined" />
                          </TableCell>
                          <TableCell><PriorityBadge priority={t.predicted_priority || t.priority} /></TableCell>
                          <TableCell>
                            <Chip label={t.ai_routed ? 'Routed' : 'Manual'} size="small" color={t.ai_routed ? 'primary' : 'default'} />
                          </TableCell>
                          <TableCell>
                            <Chip label={t.kb_match ? 'Matched' : 'None'} size="small" color={t.kb_match ? 'success' : 'default'} />
                          </TableCell>
                          <TableCell><StatusBadge status={t.status} /></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              {tab === 2 && (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Team</TableCell>
                        <TableCell>Total Tickets</TableCell>
                        <TableCell>Open</TableCell>
                        <TableCell>Closed</TableCell>
                        <TableCell>High Priority</TableCell>
                        <TableCell>AI Routed</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {teams.map((team) => {
                        const teamTickets = tickets.filter((t) => t.predicted_team === team)
                        const open = teamTickets.filter((t) => t.status?.toLowerCase() === 'open').length
                        const closed = teamTickets.filter((t) => t.status?.toLowerCase() === 'closed').length
                        const high = teamTickets.filter((t) => (t.priority || t.predicted_priority)?.toLowerCase() === 'high').length
                        const aiR = teamTickets.filter((t) => t.ai_routed).length
                        return (
                          <TableRow key={team} hover>
                            <TableCell>
                              <Typography variant="body2" fontWeight={600}>{team}</Typography>
                            </TableCell>
                            <TableCell><Typography variant="body2">{teamTickets.length}</Typography></TableCell>
                            <TableCell><Chip label={open} size="small" color="warning" variant="outlined" /></TableCell>
                            <TableCell><Chip label={closed} size="small" color="success" variant="outlined" /></TableCell>
                            <TableCell><Chip label={high} size="small" color="error" variant="outlined" /></TableCell>
                            <TableCell><Typography variant="body2">{aiR}</Typography></TableCell>
                          </TableRow>
                        )
                      })}
                      {teams.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={6} align="center">
                            <Typography variant="body2" color="text.secondary" py={3}>No team data available</Typography>
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              {tab !== 2 && (
                <TablePagination
                  component="div"
                  count={filtered.length}
                  page={page}
                  onPageChange={(_, p) => setPage(p)}
                  rowsPerPage={rowsPerPage}
                  onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value)); setPage(0) }}
                  rowsPerPageOptions={[10, 15, 25, 50]}
                />
              )}
            </>
          )}
        </CardContent>
      </Card>
    </Box>
  )
}
