import React, { useEffect, useState, useCallback } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
  Box, Typography, Card, CardContent, Button, TextField, Select, MenuItem,
  FormControl, InputLabel, Table, TableHead, TableRow, TableCell, TableBody,
  CircularProgress, Alert, Chip, Dialog, DialogTitle, DialogContent,
  DialogActions, Tabs, Tab, Divider, useTheme,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import { availabilityApi } from '../api/services'
import type { AgentShift, OnCallEntry, PublicHoliday } from '../types'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

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

export default function ShiftsPage() {
  const theme = useTheme()
  const context = useOutletContext<{ currentRole?: string }>()
  const currentRole = context?.currentRole || 'manager'
  const isPrivileged = ['manager', 'team_lead', 'admin'].includes(currentRole)

  const [tab, setTab] = useState(0)
  const [shifts, setShifts] = useState<AgentShift[]>([])
  const [oncall, setOncall] = useState<OnCallEntry[]>([])
  const [holidays, setHolidays] = useState<PublicHoliday[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Shift form
  const [shiftDialog, setShiftDialog] = useState(false)
  const [sAgentId, setSAgentId] = useState('')
  const [sWeekday, setSWeekday] = useState(0)
  const [sStart, setSStart] = useState('09:00')
  const [sEnd, setSEnd] = useState('17:00')
  const [sSubmitting, setSSubmitting] = useState(false)
  const [sError, setSError] = useState<string | null>(null)

  // On-call form
  const [oncallDialog, setOncallDialog] = useState(false)
  const [ocAgentId, setOcAgentId] = useState('')
  const [ocTeam, setOcTeam] = useState('')
  const [ocStart, setOcStart] = useState('')
  const [ocEnd, setOcEnd] = useState('')
  const [ocSubmitting, setOcSubmitting] = useState(false)
  const [ocError, setOcError] = useState<string | null>(null)

  // Holiday form
  const [holidayDialog, setHolidayDialog] = useState(false)
  const [hDate, setHDate] = useState('')
  const [hName, setHName] = useState('')
  const [hRegion, setHRegion] = useState('')
  const [hSubmitting, setHSubmitting] = useState(false)
  const [hError, setHError] = useState<string | null>(null)

  const fetchAll = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [sRes, oRes, hRes] = await Promise.all([
        availabilityApi.getShifts(),
        availabilityApi.getOnCall(),
        availabilityApi.getHolidays(),
      ])
      setShifts(Array.isArray(sRes.data) ? sRes.data : [])
      setOncall(Array.isArray(oRes.data) ? oRes.data : [])
      setHolidays(Array.isArray(hRes.data) ? hRes.data : [])
    } catch (e: any) {
      if (e?.response?.status === 403) setError('Access denied. Manager role required.')
      else setError(e?.response?.data?.detail || 'Failed to load data.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const handleAddShift = async () => {
    if (!sAgentId) { setSError('Agent ID is required.'); return }
    setSSubmitting(true); setSError(null)
    try {
      await availabilityApi.createShift({ agent_id: Number(sAgentId), weekday: sWeekday, start_time: sStart, end_time: sEnd })
      setShiftDialog(false); setSAgentId(''); setSStart('09:00'); setSEnd('17:00')
      await fetchAll()
    } catch (e: any) { setSError(e?.response?.data?.detail || 'Failed to create shift.') }
    finally { setSSubmitting(false) }
  }

  const handleDeleteShift = async (id: number) => {
    try { await availabilityApi.deleteShift(id); await fetchAll() }
    catch (e: any) { setError(e?.response?.data?.detail || 'Failed to delete shift.') }
  }

  const handleAddOncall = async () => {
    if (!ocAgentId || !ocTeam || !ocStart || !ocEnd) { setOcError('All fields required.'); return }
    setOcSubmitting(true); setOcError(null)
    try {
      const fmt = (s: string) => s.replace('T', ' ').slice(0, 16)
      await availabilityApi.createOnCall({ agent_id: Number(ocAgentId), team_name: ocTeam, start_dt: fmt(ocStart), end_dt: fmt(ocEnd) })
      setOncallDialog(false); setOcAgentId(''); setOcTeam(''); setOcStart(''); setOcEnd('')
      await fetchAll()
    } catch (e: any) { setOcError(e?.response?.data?.detail || 'Failed to create on-call entry.') }
    finally { setOcSubmitting(false) }
  }

  const handleAddHoliday = async () => {
    if (!hDate || !hName) { setHError('Date and name are required.'); return }
    setHSubmitting(true); setHError(null)
    try {
      await availabilityApi.createHoliday({ date: hDate, name: hName, region: hRegion || undefined })
      setHolidayDialog(false); setHDate(''); setHName(''); setHRegion('')
      await fetchAll()
    } catch (e: any) { setHError(e?.response?.data?.detail || 'Failed to add holiday.') }
    finally { setHSubmitting(false) }
  }

  // Group shifts by weekday for the grid
  const shiftsByDay: Record<number, AgentShift[]> = {}
  for (let i = 0; i < 7; i++) shiftsByDay[i] = []
  shifts.forEach(s => { if (shiftsByDay[s.weekday] !== undefined) shiftsByDay[s.weekday].push(s) })

  if (!isPrivileged) return (
    <Box>
      <Alert severity="warning">This page is only accessible to managers and admins.</Alert>
    </Box>
  )

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3} flexWrap="wrap" gap={1.5}>
        <Box>
          <Typography variant="h2" fontWeight={800}>Shifts & On-Call</Typography>
          <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>
            Manage agent shifts, on-call rosters, and public holidays
          </Typography>
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}
        aria-label="Shifts and on-call tabs">
        <Tab label="Weekly Shifts" id="tab-0" aria-controls="tabpanel-0" />
        <Tab label="On-Call Roster" id="tab-1" aria-controls="tabpanel-1" />
        <Tab label="Public Holidays" id="tab-2" aria-controls="tabpanel-2" />
      </Tabs>

      {loading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress size={24} style={{ color: '#2563EB' }} />
        </Box>
      ) : (
        <>
          {/* Tab 0: Weekly Shifts Grid */}
          <Box role="tabpanel" id="tabpanel-0" aria-labelledby="tab-0" hidden={tab !== 0}>
            <Box display="flex" justifyContent="flex-end" mb={2}>
              <Button variant="contained" startIcon={<AddIcon />} onClick={() => setShiftDialog(true)}
                style={{ backgroundColor: '#2563EB' }}>
                Add Shift
              </Button>
            </Box>
            <Box display="grid" gridTemplateColumns="repeat(7, 1fr)" gap={1}>
              {WEEKDAYS.map((day, idx) => (
                <Card key={day} sx={{ minHeight: 120 }}>
                  <CardContent sx={{ p: 1.5 }}>
                    <Typography variant="caption" fontWeight={800}
                      style={{ color: idx >= 5 ? '#D97706' : theme.palette.text.primary, textTransform: 'uppercase' }}>
                      {day}
                    </Typography>
                    <Divider sx={{ my: 0.5 }} />
                    {shiftsByDay[idx].length === 0 ? (
                      <Typography variant="caption" style={{ color: theme.palette.text.disabled }}>No shifts</Typography>
                    ) : (
                      shiftsByDay[idx].map(s => (
                        <Box key={s.id} display="flex" justifyContent="space-between" alignItems="center"
                          sx={{ mt: 0.5, p: 0.5, borderRadius: 1, bgcolor: theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B' }}>
                          <Box>
                            <Typography variant="caption" fontWeight={700} display="block">{s.agent_name}</Typography>
                            <Typography variant="caption" style={{ color: '#2563EB' }}>
                              {s.start_time}–{s.end_time}
                              {s.end_time < s.start_time && ' (overnight)'}
                            </Typography>
                          </Box>
                          <Button size="small" onClick={() => handleDeleteShift(s.id)}
                            style={{ minWidth: 0, padding: 2, color: '#DC2626' }}
                            aria-label={`Delete shift for ${s.agent_name}`}>
                            <DeleteIcon style={{ fontSize: 14 }} />
                          </Button>
                        </Box>
                      ))
                    )}
                  </CardContent>
                </Card>
              ))}
            </Box>
          </Box>

          {/* Tab 1: On-Call */}
          <Box role="tabpanel" id="tabpanel-1" aria-labelledby="tab-1" hidden={tab !== 1}>
            <Box display="flex" justifyContent="flex-end" mb={2}>
              <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOncallDialog(true)}
                style={{ backgroundColor: '#2563EB' }}>
                Add On-Call Entry
              </Button>
            </Box>
            {oncall.length === 0 ? (
              <Box textAlign="center" py={6}>
                <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>No on-call entries.</Typography>
              </Box>
            ) : (
              <Card>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Agent</TableCell>
                      <TableCell>Team</TableCell>
                      <TableCell>From</TableCell>
                      <TableCell>To</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {oncall.map(o => (
                      <TableRow key={o.id} hover>
                        <TableCell style={{ fontWeight: 600 }}>{o.agent_name}</TableCell>
                        <TableCell><Chip label={o.team} size="small" style={{ backgroundColor: theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B', color: '#2563EB' }} /></TableCell>
                        <TableCell style={{ color: theme.palette.text.secondary }}>{fmtDate(o.start)}</TableCell>
                        <TableCell style={{ color: theme.palette.text.secondary }}>{fmtDate(o.end)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            )}
          </Box>

          {/* Tab 2: Holidays */}
          <Box role="tabpanel" id="tabpanel-2" aria-labelledby="tab-2" hidden={tab !== 2}>
            <Box display="flex" justifyContent="flex-end" mb={2}>
              <Button variant="contained" startIcon={<AddIcon />} onClick={() => setHolidayDialog(true)}
                style={{ backgroundColor: '#2563EB' }}>
                Add Holiday
              </Button>
            </Box>
            {holidays.length === 0 ? (
              <Box textAlign="center" py={6}>
                <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>No holidays configured.</Typography>
              </Box>
            ) : (
              <Card>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Date</TableCell>
                      <TableCell>Name</TableCell>
                      <TableCell>Region</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {holidays.map(h => (
                      <TableRow key={h.id} hover>
                        <TableCell style={{ fontWeight: 700, color: '#2563EB' }}>{h.date}</TableCell>
                        <TableCell>{h.name}</TableCell>
                        <TableCell>
                          {h.region
                            ? <Chip label={h.region} size="small" style={{ backgroundColor: '#F1F5F9', fontWeight: 600 }} />
                            : <Typography variant="caption" style={{ color: theme.palette.text.disabled }}>All regions</Typography>}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            )}
          </Box>
        </>
      )}

      {/* Add Shift Dialog */}
      <Dialog open={shiftDialog} onClose={() => setShiftDialog(false)} maxWidth="xs" fullWidth
        aria-labelledby="shift-dialog-title">
        <DialogTitle id="shift-dialog-title">Add Shift</DialogTitle>
        <DialogContent>
          {sError && <Alert severity="error" sx={{ mb: 2 }}>{sError}</Alert>}
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            <TextField label="Agent ID *" type="number" fullWidth value={sAgentId}
              onChange={(e) => setSAgentId(e.target.value)} />
            <FormControl fullWidth>
              <InputLabel id="weekday-label">Day of Week</InputLabel>
              <Select labelId="weekday-label" value={sWeekday} label="Day of Week"
                onChange={(e) => setSWeekday(Number(e.target.value))}>
                {WEEKDAYS.map((d, i) => <MenuItem key={i} value={i}>{d}</MenuItem>)}
              </Select>
            </FormControl>
            <TextField label="Start time (HH:MM)" fullWidth value={sStart}
              onChange={(e) => setSStart(e.target.value)} placeholder="09:00" />
            <TextField label="End time (HH:MM)" fullWidth value={sEnd}
              onChange={(e) => setSEnd(e.target.value)} placeholder="17:00"
              helperText="For overnight shifts, set end time before start (e.g. 22:00–06:00)" />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setShiftDialog(false)} disabled={sSubmitting}>Cancel</Button>
          <Button variant="contained" onClick={handleAddShift} disabled={sSubmitting}
            style={{ backgroundColor: '#2563EB' }}>
            {sSubmitting ? <CircularProgress size={16} style={{ color: '#fff' }} /> : 'Add Shift'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add On-Call Dialog */}
      <Dialog open={oncallDialog} onClose={() => setOncallDialog(false)} maxWidth="xs" fullWidth
        aria-labelledby="oncall-dialog-title">
        <DialogTitle id="oncall-dialog-title">Add On-Call Entry</DialogTitle>
        <DialogContent>
          {ocError && <Alert severity="error" sx={{ mb: 2 }}>{ocError}</Alert>}
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            <TextField label="Agent ID *" type="number" fullWidth value={ocAgentId}
              onChange={(e) => setOcAgentId(e.target.value)} />
            <TextField label="Team Name *" fullWidth value={ocTeam}
              onChange={(e) => setOcTeam(e.target.value)} />
            <TextField label="Start *" type="datetime-local" fullWidth value={ocStart}
              onChange={(e) => setOcStart(e.target.value)} InputLabelProps={{ shrink: true }} />
            <TextField label="End *" type="datetime-local" fullWidth value={ocEnd}
              onChange={(e) => setOcEnd(e.target.value)} InputLabelProps={{ shrink: true }} />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setOncallDialog(false)} disabled={ocSubmitting}>Cancel</Button>
          <Button variant="contained" onClick={handleAddOncall} disabled={ocSubmitting}
            style={{ backgroundColor: '#2563EB' }}>
            {ocSubmitting ? <CircularProgress size={16} style={{ color: '#fff' }} /> : 'Add Entry'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add Holiday Dialog */}
      <Dialog open={holidayDialog} onClose={() => setHolidayDialog(false)} maxWidth="xs" fullWidth
        aria-labelledby="holiday-dialog-title">
        <DialogTitle id="holiday-dialog-title">Add Public Holiday</DialogTitle>
        <DialogContent>
          {hError && <Alert severity="error" sx={{ mb: 2 }}>{hError}</Alert>}
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            <TextField label="Date *" type="date" fullWidth value={hDate}
              onChange={(e) => setHDate(e.target.value)} InputLabelProps={{ shrink: true }} />
            <TextField label="Holiday Name *" fullWidth value={hName}
              onChange={(e) => setHName(e.target.value)} />
            <TextField label="Region (optional)" fullWidth value={hRegion}
              onChange={(e) => setHRegion(e.target.value)}
              placeholder="e.g. Asia/Kolkata, US — leave blank for all regions" />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setHolidayDialog(false)} disabled={hSubmitting}>Cancel</Button>
          <Button variant="contained" onClick={handleAddHoliday} disabled={hSubmitting}
            style={{ backgroundColor: '#2563EB' }}>
            {hSubmitting ? <CircularProgress size={16} style={{ color: '#fff' }} /> : 'Add Holiday'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
