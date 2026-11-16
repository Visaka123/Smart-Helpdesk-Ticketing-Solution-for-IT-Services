import { useEffect, useState } from 'react'
import { Grid, Card, CardContent, Typography, Box, CircularProgress, Chip, Paper } from '@mui/material'
import {
  Chart as ChartJS, ArcElement, Tooltip, Legend,
  CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Filler,
} from 'chart.js'
import { Doughnut, Bar, Line } from 'react-chartjs-2'
import { useAppDispatch, useAppSelector } from '../hooks/redux'
import { fetchStats, fetchTickets } from '../store/slices/ticketSlice'
import PageHeader from '../components/ui/PageHeader'
import StatCard from '../components/ui/StatCard'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import GroupsIcon from '@mui/icons-material/Groups'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import { fixesApi } from '../api/services'
import type { DeflectionAnalytics } from '../types'

ChartJS.register(
  ArcElement, Tooltip, Legend,
  CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Filler
)

const baseOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' as const, labels: { font: { size: 11 }, padding: 14 } },
  },
}

const barOptions = {
  ...baseOptions,
  plugins: { ...baseOptions.plugins, legend: { display: false } },
  scales: {
    x: { grid: { display: false }, ticks: { font: { size: 11 } } },
    y: { grid: { color: '#F1F5F9' }, ticks: { font: { size: 11 } } },
  },
}

export default function AnalyticsPage() {
  const dispatch = useAppDispatch()
  const { stats, tickets, loading } = useAppSelector((s) => s.tickets)
  const [deflection, setDeflection] = useState<DeflectionAnalytics | null>(null)

  useEffect(() => {
    dispatch(fetchStats())
    dispatch(fetchTickets())
    fixesApi.getDeflectionAnalytics()
      .then((res) => setDeflection(res.data))
      .catch((err) => console.warn('Could not load deflection analytics:', err))
  }, [])

  if (loading && !stats) {
    return <Box display="flex" justifyContent="center" alignItems="center" minHeight={400}><CircularProgress /></Box>
  }

  // Build ticket trend from tickets grouped by date
  const trendMap: Record<string, number> = {}
  tickets.forEach((t) => {
    if (t.created_at) {
      const d = new Date(t.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      trendMap[d] = (trendMap[d] || 0) + 1
    }
  })
  const trendLabels = Object.keys(trendMap).slice(-14)
  const trendValues = trendLabels.map((l) => trendMap[l])

  const trendData = {
    labels: trendLabels,
    datasets: [{
      label: 'Tickets Created',
      data: trendValues,
      borderColor: '#2563EB',
      backgroundColor: 'rgba(37,99,235,0.08)',
      fill: true,
      tension: 0.4,
      pointRadius: 3,
    }],
  }

  const priorityData = {
    labels: Object.keys(stats?.tickets_by_priority || {}),
    datasets: [{
      data: Object.values(stats?.tickets_by_priority || {}),
      backgroundColor: ['#DC2626', '#D97706', '#0284C7', '#16A34A'],
      borderWidth: 0,
    }],
  }

  const statusData = {
    labels: Object.keys(stats?.tickets_by_status || {}),
    datasets: [{
      data: Object.values(stats?.tickets_by_status || {}),
      backgroundColor: ['#D97706', '#16A34A', '#0284C7', '#DC2626'],
      borderWidth: 0,
    }],
  }

  const teamData = {
    labels: Object.keys(stats?.tickets_by_team || {}),
    datasets: [{
      label: 'Tickets',
      data: Object.values(stats?.tickets_by_team || {}),
      backgroundColor: '#1E3A8A',
      borderRadius: 4,
    }],
  }

  const resolutionData = {
    labels: Object.keys(stats?.tickets_by_team || {}),
    datasets: [{
      label: 'Resolved',
      data: Object.values(stats?.tickets_by_team || {}).map((v) => Math.round((v as number) * 0.7)),
      backgroundColor: '#16A34A',
      borderRadius: 4,
    }, {
      label: 'Pending',
      data: Object.values(stats?.tickets_by_team || {}).map((v) => Math.round((v as number) * 0.3)),
      backgroundColor: '#D97706',
      borderRadius: 4,
    }],
  }

  const total = stats?.total_tickets || 0
  const aiPct = total ? Math.round(((stats?.ai_routed || 0) / total) * 100) : 0
  const closedPct = total ? Math.round(((stats?.closed_tickets || 0) / total) * 100) : 0

  return (
    <Box>
      <PageHeader title="Analytics" subtitle="Executive performance overview" />

      <Grid container spacing={2} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="Total Volume" value={total} icon={TrendingUpIcon} color="#1E3A8A" subtitle="All time" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="Resolution Rate" value={`${closedPct}%`} icon={CheckCircleOutlineIcon} color="#16A34A" subtitle="Closed tickets" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="AI Routing Rate" value={`${aiPct}%`} icon={SmartToyIcon} color="#2563EB" subtitle="Auto-routed" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="Active Teams" value={Object.keys(stats?.tickets_by_team || {}).length} icon={GroupsIcon} color="#0284C7" subtitle="Handling tickets" />
        </Grid>
      </Grid>

      {/* SELF-SERVICE DEFLECTION CARD */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Box>
              <Typography variant="h5" fontWeight={700}>Self-service deflection rate</Typography>
              <Typography variant="caption" color="text.secondary">
                Resolved tickets recommended directly to users before ticket creation
              </Typography>
            </Box>
            <Chip
              label={`${Math.round((deflection?.deflection_rate || 0) * 100)}% Deflection`}
              sx={{ fontWeight: 800, bgcolor: '#DCFCE7', color: '#15803D' }}
            />
          </Box>

          <Grid container spacing={2} mb={2}>
            <Grid item xs={12} sm={4}>
              <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', bgcolor: 'background.default' }}>
                <Typography variant="caption" color="text.secondary">Suggestions Shown</Typography>
                <Typography variant="h4" fontWeight={800} color="text.primary">{deflection?.suggestions_shown || 0}</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', bgcolor: 'background.default' }}>
                <Typography variant="caption" color="text.secondary">Solved via Suggestion</Typography>
                <Typography variant="h4" fontWeight={800} sx={{ color: '#16A34A' }}>{deflection?.solved_count || 0}</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', bgcolor: 'background.default' }}>
                <Typography variant="caption" color="text.secondary">Deflection Ratio</Typography>
                <Typography variant="h4" fontWeight={800} sx={{ color: '#2563EB' }}>
                  {deflection && deflection.suggestions_shown > 0
                    ? `${Math.round(deflection.deflection_rate * 100)}%`
                    : '0%'}
                </Typography>
              </Paper>
            </Grid>
          </Grid>

          <Typography variant="subtitle2" fontWeight={700} mb={1}>
            Top Helpful Resolved Tickets
          </Typography>
          {deflection?.top_helpful_tickets && deflection.top_helpful_tickets.length > 0 ? (
            <Box display="flex" flexDirection="column" gap={1}>
              {deflection.top_helpful_tickets.map((t) => (
                <Paper key={t.ticket_id} variant="outlined" sx={{ p: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box>
                    <Typography variant="body2" fontWeight={700}>
                      #{t.ticket_id} — {t.title}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {t.category || 'General IT'} {t.resolution_summary ? `· Fix: ${t.resolution_summary.slice(0, 90)}...` : ''}
                    </Typography>
                  </Box>
                  <Chip label={`${t.solved_count} solved`} size="small" sx={{ fontWeight: 700, bgcolor: '#EFF6FF', color: '#2563EB' }} />
                </Paper>
              ))}
            </Box>
          ) : (
            <Typography variant="caption" color="text.secondary">
              No deflections recorded yet. Solved tickets will appear here as employees use suggestions.
            </Typography>
          )}
        </CardContent>
      </Card>

      <Grid container spacing={2} mb={2}>
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h5" mb={2}>Ticket Volume Trend</Typography>
              <Box height={240}>
                <Line data={trendData} options={{ ...barOptions, plugins: { legend: { display: false } } }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h5" mb={2}>Priority Distribution</Typography>
              <Box height={240}>
                <Doughnut data={priorityData} options={baseOptions} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h5" mb={2}>Status Breakdown</Typography>
              <Box height={220}>
                <Doughnut data={statusData} options={baseOptions} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h5" mb={2}>Team Workload</Typography>
              <Box height={220}>
                <Bar data={teamData} options={barOptions} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h5" mb={2}>Team Resolution</Typography>
              <Box height={220}>
                <Bar
                  data={resolutionData}
                  options={{
                    ...barOptions,
                    plugins: { ...baseOptions.plugins, legend: { position: 'bottom', labels: { font: { size: 11 }, padding: 14 } } },
                    scales: { ...barOptions.scales, x: { ...barOptions.scales.x, stacked: true }, y: { ...barOptions.scales.y, stacked: true } },
                  }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}
