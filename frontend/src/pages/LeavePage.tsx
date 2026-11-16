import React, { useEffect, useState, useCallback } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
  Box, Typography, Card, CardContent, Button, TextField, Select, MenuItem,
  FormControl, InputLabel, Table, TableHead, TableRow, TableCell, TableBody,
  CircularProgress, Alert, Chip, Dialog, DialogTitle, DialogContent,
  DialogActions, useTheme,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import CheckIcon from '@mui/icons-material/Check'
import CloseIcon from '@mui/icons-material/Close'
import RefreshIcon from '@mui/icons-material/Refresh'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import { availabilityApi } from '../api/services'
import type { LeaveRequest, SyncStatus } from '../types'

// Show times in the user's local timezone
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

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  pending:   { bg: '#FEF3C7', color: '#B45309' },
  approved:  { bg: '#ECFDF5', color: '#047857' },
  cancelled: { bg: '#F1F5F9', color: '#475569' },
}

export default function LeavePage() {
  const theme = useTheme()
  const context = useOutletContext<{ currentRole?: string }>()
  const currentRole = context?.currentRole || 'agent'
  const isPrivileged = ['manager', 'team_lead', 'admin'].includes(currentRole)

  const getCaller = () => {
    const raw = localStorage.getItem('user')
    if (raw) {
      try {
        const u = JSON.parse(raw)
        return { name: u.name || 'Agent', id: u.id ? Number(u.id) : null }
      } catch {}
    }
    if (currentRole === 'agent') return { name: 'Sarah Agent', id: 3 }
    if (currentRole === 'manager') return { name: 'John Manager', id: 2 }
    return { name: 'Alice Employee', id: 5 }
  }
  const { name: callerName, id: callerId } = getCaller()

  const [leaves, setLeaves] = useState<LeaveRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Apply form
  const [formOpen, setFormOpen] = useState(false)
  const [targetAgentId, setTargetAgentId] = useState<number | ''>('')
  const [availableAgents, setAvailableAgents] = useState<{ id: number; name: string }[]>([])
  const [startDt, setStartDt] = useState('')
  const [endDt, setEndDt] = useState('')
  const [leaveType, setLeaveType] = useState('annual')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  // Approve/cancel confirmation
  const [confirmLeave, setConfirmLeave] = useState<LeaveRequest | null>(null)
  const [confirmAction, setConfirmAction] = useState<'approved' | 'cancelled'>('approved')
  const [confirmLoading, setConfirmLoading] = useState(false)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [rerouteCount, setRerouteCount] = useState<number | null>(null)
  const [rerouteLoading, setRerouteLoading] = useState(false)

  // HR Sync state
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState<string | null>(null)

  // Emergency Unavailable Modal
  const [emergencyOpen, setEmergencyOpen] = useState(false)
  const [emergencyLoading, setEmergencyLoading] = useState(false)

  const fetchSyncStatus = useCallback(async () => {
    try {
      const res = await availabilityApi.getSyncStatus()
      setSyncStatus(res.data)
    } catch {}
  }, [])

  const fetchLeaves = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const res = await availabilityApi.getLeave()
      setLeaves(Array.isArray(res.data) ? res.data : [])
    } catch (e: any) {
      if (e?.response?.status === 403) setError('Access denied.')
      else setError(e?.response?.data?.detail || 'Failed to load leave requests.')
      setLeaves([])
    } finally { setLoading(false) }
  }, [currentRole])

  useEffect(() => {
    fetchLeaves()
    fetchSyncStatus()
  }, [fetchLeaves, fetchSyncStatus, currentRole])

  const handleSyncNow = async () => {
    setSyncing(true)
    setSyncMsg(null)
    try {
      const res: any = await availabilityApi.syncNow()
      setSyncMsg(`HR Sync completed: ${res.data.synced} records updated, ${res.data.cancelled} cancelled.`)
      await Promise.all([fetchLeaves(), fetchSyncStatus()])
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  const handleMarkEmergency = async () => {
    setEmergencyLoading(true)
    try {
      const res: any = await availabilityApi.emergencyUnavailable()
      setEmergencyOpen(false)
      setSyncMsg(res.data.message || 'Marked unavailable for today.')
      await fetchLeaves()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to mark emergency unavailability.')
    } finally {
      setEmergencyLoading(false)
    }
  }

  const handleOpenApply = async () => {
    setFormOpen(true)
    if (isPrivileged && availableAgents.length === 0) {
      try {
        const res = await availabilityApi.getAvailableNow()
        if (Array.isArray(res.data)) {
          setAvailableAgents(res.data.map((a: any) => ({ id: a.id, name: a.name })))
          if (res.data.length > 0 && !targetAgentId) {
            setTargetAgentId(res.data[0].id)
          }
        }
      } catch {}
    }
  }

  const handleApply = async () => {
    if (!startDt || !endDt) { setFormError('Start and end date/time are required.'); return }
    const effectiveAgentId = (isPrivileged && targetAgentId) ? Number(targetAgentId) : (callerId || (currentRole === 'agent' ? 3 : 2))
    setSubmitting(true); setFormError(null)
    try {
      const fmt = (s: string) => s.replace('T', ' ').slice(0, 16)
      await availabilityApi.createLeave({
        agent_id: effectiveAgentId,
        start_datetime: fmt(startDt),
        end_datetime: fmt(endDt),
        leave_type: leaveType,
        notes,
      })
      setFormOpen(false)
      setStartDt(''); setEndDt(''); setNotes(''); setLeaveType('annual')
      await fetchLeaves()
    } catch (e: any) {
      setFormError(e?.response?.data?.detail || 'Failed to submit leave request.')
    } finally { setSubmitting(false) }
  }

  const openConfirm = async (leave: LeaveRequest, action: 'approved' | 'cancelled') => {
    setConfirmLeave(leave)
    setConfirmAction(action)
    setConfirmError(null)
    setRerouteCount(null)

    // Fetch reroute count only when approving
    if (action === 'approved') {
      setRerouteLoading(true)
      try {
        const res = await availabilityApi.getRerouteCount(leave.id)
        setRerouteCount(res.data.reroute_count)
      } catch {
        setRerouteCount(null) // non-fatal — show confirmation without count
      } finally {
        setRerouteLoading(false)
      }
    }
  }

  const handleConfirmAction = async () => {
    if (!confirmLeave) return
    setConfirmLoading(true); setConfirmError(null)
    try {
      await availabilityApi.approveLeave(confirmLeave.id, confirmAction, callerName)
      setConfirmLeave(null)
      await fetchLeaves()
    } catch (e: any) {
      if (e?.response?.status === 403) {
        setConfirmError('You do not have permission to perform this action.')
      } else {
        setConfirmError(e?.response?.data?.detail || 'Action failed.')
      }
    } finally { setConfirmLoading(false) }
  }

  const safeLeaves = Array.isArray(leaves) ? leaves : []
  const pendingCount = safeLeaves.filter(l => l.status === 'pending').length

  // Detect user's local timezone name for display
  const localTz = Intl.DateTimeFormat().resolvedOptions().timeZone

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Box display="flex" alignItems="center" gap={1.5} mb={0.5}>
            <Typography variant="h2" fontWeight={800}>Leave Requests</Typography>
            {syncStatus && (
              <Chip
                label={syncStatus.minutes_since_sync !== null ? `Last synced ${syncStatus.minutes_since_sync} min ago` : 'Never synced'}
                size="small"
                variant="outlined"
                color={syncStatus.stale ? 'warning' : 'default'}
                style={{ fontWeight: 600 }}
              />
            )}
          </Box>
          <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>
            {isPrivileged
              ? `All agents — ${pendingCount} pending approval`
              : 'Your leave requests'}{' '}
            <Typography component="span" variant="caption" style={{ color: theme.palette.text.disabled }}>
              (times shown in {localTz})
            </Typography>
          </Typography>
        </Box>
        <Box display="flex" gap={1.5} alignItems="center">
          {isPrivileged && (
            <Button
              variant="outlined"
              startIcon={syncing ? <CircularProgress size={16} /> : <RefreshIcon />}
              onClick={handleSyncNow}
              disabled={syncing}
              style={{ fontWeight: 700 }}
            >
              {syncing ? 'Syncing...' : 'Sync Now'}
            </Button>
          )}
          {syncStatus?.sync_enabled ? (
            <Button
              variant="contained"
              color="warning"
              startIcon={<WarningAmberIcon />}
              onClick={() => setEmergencyOpen(true)}
              style={{ fontWeight: 700 }}
            >
              Mark Me Unavailable
            </Button>
          ) : (
            <Button variant="contained" startIcon={<AddIcon />} onClick={handleOpenApply}
              style={{ backgroundColor: '#2563EB', fontWeight: 700 }}>
              Apply for Leave
            </Button>
          )}
        </Box>
      </Box>

      {syncStatus?.stale && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          ⚠️ Warning: HR Leave sync is delayed. Last synced over 60 minutes ago.
        </Alert>
      )}

      {syncMsg && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSyncMsg(null)}>
          {syncMsg}
        </Alert>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Card>
        <CardContent>
          {loading ? (
            <Box display="flex" justifyContent="center" py={6}>
              <CircularProgress size={24} style={{ color: '#2563EB' }} />
            </Box>
          ) : safeLeaves.length === 0 ? (
            <Box textAlign="center" py={6}>
              <Typography variant="body2" style={{ color: theme.palette.text.secondary }}>
                No leave requests found.
              </Typography>
            </Box>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  {isPrivileged && <TableCell>Agent</TableCell>}
                  <TableCell>Type</TableCell>
                  <TableCell>From</TableCell>
                  <TableCell>To</TableCell>
                  <TableCell>Notes</TableCell>
                  <TableCell>Status</TableCell>
                  {isPrivileged && <TableCell>Actions</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {safeLeaves.map((l) => {
                  const sc = STATUS_COLORS[l.status] || STATUS_COLORS.pending
                  return (
                    <TableRow key={l.id} hover>
                      {isPrivileged && <TableCell style={{ fontWeight: 600 }}>{l.agent_name}</TableCell>}
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Chip label={l.type} size="small"
                            style={{ backgroundColor: theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B', color: '#2563EB', fontWeight: 600 }} />
                          {l.source === 'hr_sync' && (
                            <Chip label="Synced from HR" size="small" variant="outlined" color="primary"
                              style={{ height: 20, fontSize: '0.65rem', fontWeight: 700 }} />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell style={{ color: theme.palette.text.secondary }}>{fmtDate(l.start)}</TableCell>
                      <TableCell style={{ color: theme.palette.text.secondary }}>{fmtDate(l.end)}</TableCell>
                      <TableCell>
                        <Typography variant="caption" noWrap style={{ color: theme.palette.text.secondary, maxWidth: 180, display: 'block' }}>
                          {l.notes || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={l.status.toUpperCase()} size="small"
                          style={{ backgroundColor: sc.bg, color: sc.color, fontWeight: 700 }} />
                      </TableCell>
                      {isPrivileged && (
                        <TableCell>
                          <Box display="flex" gap={1}>
                            {l.status === 'pending' && (
                              <Button size="small" variant="outlined" color="success"
                                startIcon={<CheckIcon />}
                                onClick={() => openConfirm(l, 'approved')}
                                style={{ padding: '2px 8px' }}>
                                Approve
                              </Button>
                            )}
                            {(l.status === 'pending' || l.status === 'approved') && (
                              <Button size="small" variant="outlined" color="error"
                                startIcon={<CloseIcon />}
                                onClick={() => openConfirm(l, 'cancelled')}
                                style={{ padding: '2px 8px' }}>
                                Cancel
                              </Button>
                            )}
                          </Box>
                        </TableCell>
                      )}
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Apply Dialog */}
      <Dialog open={formOpen} onClose={() => setFormOpen(false)} maxWidth="sm" fullWidth
        aria-labelledby="leave-form-title">
        <DialogTitle id="leave-form-title">Apply for Leave</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mb: 2 }}>{formError}</Alert>}
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            {isPrivileged && availableAgents.length > 0 && (
              <FormControl fullWidth>
                <InputLabel id="target-agent-label">Agent *</InputLabel>
                <Select
                  labelId="target-agent-label"
                  value={targetAgentId}
                  label="Agent *"
                  onChange={(e) => setTargetAgentId(Number(e.target.value))}
                >
                  {availableAgents.map((a) => (
                    <MenuItem key={a.id} value={a.id}>
                      {a.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
            <FormControl fullWidth>
              <InputLabel id="leave-type-label">Leave Type</InputLabel>
              <Select labelId="leave-type-label" value={leaveType} label="Leave Type"
                onChange={(e) => setLeaveType(e.target.value)}>
                <MenuItem value="annual">Annual Leave</MenuItem>
                <MenuItem value="sick">Sick Leave</MenuItem>
                <MenuItem value="half_day_am">Half Day — AM</MenuItem>
                <MenuItem value="half_day_pm">Half Day — PM</MenuItem>
              </Select>
            </FormControl>
            <TextField label="Start date & time *" type="datetime-local" fullWidth
              value={startDt} onChange={(e) => setStartDt(e.target.value)}
              InputLabelProps={{ shrink: true }}
              helperText={`Your timezone: ${localTz}`} />
            <TextField label="End date & time *" type="datetime-local" fullWidth
              value={endDt} onChange={(e) => setEndDt(e.target.value)}
              InputLabelProps={{ shrink: true }} />
            <TextField label="Reason / Notes" fullWidth multiline minRows={2}
              value={notes} onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional — e.g. medical appointment, family event…" />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setFormOpen(false)} disabled={submitting}>Cancel</Button>
          <Button variant="contained" onClick={handleApply} disabled={submitting}
            style={{ backgroundColor: '#2563EB' }}>
            {submitting ? <CircularProgress size={16} style={{ color: '#fff' }} /> : 'Submit Request'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirm Dialog */}
      <Dialog open={!!confirmLeave} onClose={() => setConfirmLeave(null)} maxWidth="xs" fullWidth
        aria-labelledby="confirm-title">
        <DialogTitle id="confirm-title">
          {confirmAction === 'approved' ? 'Approve Leave' : 'Cancel Leave'}
        </DialogTitle>
        <DialogContent>
          {confirmError && <Alert severity="error" sx={{ mb: 2 }}>{confirmError}</Alert>}
          {confirmLeave && (
            <Box>
              <Typography variant="body2" mb={1}>
                {confirmAction === 'approved'
                  ? `Approve leave for ${confirmLeave.agent_name}?`
                  : `Cancel leave for ${confirmLeave.agent_name}?`}
              </Typography>
              <Typography variant="caption" style={{ color: theme.palette.text.secondary }}>
                {fmtDate(confirmLeave.start)} → {fmtDate(confirmLeave.end)}
              </Typography>
              {confirmAction === 'approved' && (
                <Alert severity="info" sx={{ mt: 2 }} icon={false}>
                  {rerouteLoading ? (
                    <Box display="flex" alignItems="center" gap={1}>
                      <CircularProgress size={12} />
                      <span>Checking tickets to reroute…</span>
                    </Box>
                  ) : rerouteCount !== null ? (
                    rerouteCount === 0
                      ? 'No unstarted tickets to reroute.'
                      : `${rerouteCount} unstarted ticket${rerouteCount !== 1 ? 's' : ''} will be automatically rerouted to another available agent.`
                  ) : (
                    'Approving will trigger automatic rerouting of this agent\'s unstarted tickets.'
                  )}
                </Alert>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setConfirmLeave(null)} disabled={confirmLoading}>Back</Button>
          <Button variant="contained"
            color={confirmAction === 'approved' ? 'success' : 'error'}
            onClick={handleConfirmAction} disabled={confirmLoading || rerouteLoading}>
            {confirmLoading
              ? <CircularProgress size={16} style={{ color: '#fff' }} />
              : confirmAction === 'approved' ? 'Approve' : 'Cancel Leave'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Emergency Unavailable Dialog */}
      <Dialog open={emergencyOpen} onClose={() => setEmergencyOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Mark Me Unavailable (Emergency)</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            This will mark you unavailable for <strong>today only</strong> due to an immediate emergency.
            Active and unstarted tickets assigned to you will be immediately re-routed to available colleagues.
          </Typography>
          <Alert severity="info">
            All scheduled vacation or sick leaves should be submitted through the enterprise HR portal.
          </Alert>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEmergencyOpen(false)} disabled={emergencyLoading}>Cancel</Button>
          <Button
            variant="contained"
            color="warning"
            onClick={handleMarkEmergency}
            disabled={emergencyLoading}
            style={{ fontWeight: 700 }}
          >
            {emergencyLoading ? 'Marking...' : 'Confirm Emergency'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
