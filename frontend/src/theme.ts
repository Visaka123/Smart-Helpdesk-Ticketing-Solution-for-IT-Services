import { createTheme } from '@mui/material/styles'

export const getAppTheme = (mode: 'light' | 'dark' = 'light') =>
  createTheme({
    palette: {
      mode,
      primary: {
        main: '#2563EB', // Professional Deep Indigo / Blue Accent
        light: '#60A5FA',
        dark: '#1D4ED8',
        contrastText: '#FFFFFF',
      },
      secondary: {
        main: '#6366F1',
        light: '#818CF8',
        dark: '#4F46E5',
      },
      background: {
        default: mode === 'light' ? '#F8FAFC' : '#0F172A',
        paper: mode === 'light' ? '#FFFFFF' : '#1E293B',
      },
      text: {
        primary: mode === 'light' ? '#0F172A' : '#F8FAFC',
        secondary: mode === 'light' ? '#475569' : '#94A3B8',
      },
      divider: mode === 'light' ? '#E2E8F0' : '#334155',

      // Semantic System Colors (Consistent across all badges)
      error: { main: '#DC2626' },    // Critical / Breached (Red)
      warning: { main: '#D97706' },  // High / At-Risk (Amber/Orange)
      info: { main: '#F59E0B' },     // Medium Priority (Amber/Yellow)
      success: { main: '#10B981' },  // Low Priority / Resolved (Emerald Green)
    },
    typography: {
      fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      h1: { fontWeight: 800, fontSize: '2.1rem', letterSpacing: '-0.02em' },
      h2: { fontWeight: 700, fontSize: '1.6rem', letterSpacing: '-0.01em' },
      h3: { fontWeight: 700, fontSize: '1.25rem' },
      h4: { fontWeight: 600, fontSize: '1.1rem' },
      h5: { fontWeight: 600, fontSize: '1rem' },
      h6: { fontWeight: 600, fontSize: '0.875rem' },
      body1: { fontSize: '0.875rem', lineHeight: 1.5 },
      body2: { fontSize: '0.8125rem', lineHeight: 1.45 },
      caption: { fontSize: '0.75rem' },
    },
    shape: { borderRadius: 8 },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 600,
            borderRadius: 6,
            boxShadow: 'none',
            '&:hover': {
              boxShadow: '0 2px 6px rgba(37, 99, 235, 0.25)',
            },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundColor: mode === 'light' ? '#FFFFFF' : '#1E293B',
            border: mode === 'light' ? '1px solid #E2E8F0' : '1px solid #334155',
            borderRadius: 8,
            boxShadow: mode === 'light' ? '0 1px 3px rgba(0,0,0,0.05)' : '0 2px 8px rgba(0,0,0,0.3)',
            transition: 'all 0.2s ease-in-out',
            '&:hover': {
              borderColor: mode === 'light' ? '#CBD5E1' : '#475569',
              boxShadow: mode === 'light' ? '0 4px 12px rgba(0,0,0,0.08)' : '0 4px 16px rgba(0,0,0,0.4)',
            },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            fontWeight: 600,
            fontSize: '0.75rem',
            borderRadius: 6,
          },
        },
      },
      MuiTableHead: {
        styleOverrides: {
          root: {
            '& .MuiTableCell-head': {
              backgroundColor: mode === 'light' ? '#F1F5F9' : '#0F172A',
              color: mode === 'light' ? '#475569' : '#94A3B8',
              fontWeight: 700,
              fontSize: '0.75rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              borderBottom: mode === 'light' ? '1px solid #E2E8F0' : '1px solid #334155',
            },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            borderBottom: mode === 'light' ? '1px solid #F1F5F9' : '1px solid #1E293B',
            padding: '12px 16px',
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            backgroundColor: mode === 'light' ? '#FFFFFF' : '#0F172A',
            borderRadius: 6,
            '& fieldset': { borderColor: mode === 'light' ? '#CBD5E1' : '#334155' },
            '&:hover fieldset': { borderColor: mode === 'light' ? '#94A3B8' : '#64748B' },
            '&.Mui-focused fieldset': { borderColor: '#2563EB' },
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundColor: mode === 'light' ? '#FFFFFF' : '#0F172A',
            color: mode === 'light' ? '#0F172A' : '#F8FAFC',
            borderBottom: mode === 'light' ? '1px solid #E2E8F0' : '1px solid #1E293B',
            boxShadow: 'none',
          },
        },
      },
    },
  })

export const theme = getAppTheme('light')
