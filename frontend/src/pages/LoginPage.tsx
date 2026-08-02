import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import {
  Box, Card, CardContent, TextField, Button, Typography,
  Alert, CircularProgress, Checkbox, FormControlLabel, Divider,
} from '@mui/material'
import LockOutlinedIcon from '@mui/icons-material/LockOutlined'
import { useAppDispatch, useAppSelector } from '../hooks/redux'
import { loginThunk, clearError } from '../store/slices/authSlice'

interface LoginForm {
  email: string
  password: string
  rememberMe: boolean
}

export default function LoginPage() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const { user, loading, error } = useAppSelector((s) => s.auth)

  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>({
    defaultValues: { email: '', password: '', rememberMe: false },
  })

  useEffect(() => {
    if (user) navigate('/dashboard', { replace: true })
    return () => { dispatch(clearError()) }
  }, [user])

  const onSubmit = (data: LoginForm) => {
    dispatch(loginThunk({ email: data.email, password: data.password }))
  }

  return (
    <Box display="flex" minHeight="100vh">
      {/* Left branding panel */}
      <Box
        sx={{
          flex: 1,
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'flex-start',
          px: 8,
          background: 'linear-gradient(160deg, #0F172A 0%, #1E3A8A 100%)',
        }}
      >
        <Typography variant="h1" color="#F8FAFC" fontWeight={700} mb={2}>
          SmartDesk
        </Typography>
        <Typography variant="h4" color="#93C5FD" fontWeight={400} mb={4}>
          Your Company IT Support Portal
        </Typography>
        <Divider sx={{ borderColor: '#1E3A8A', width: 60, mb: 4 }} />
        {[
          'Raise IT support tickets in seconds',
          'Track your request status in real time',
          'Get instant answers from the AI assistant',
          'Powered by your company knowledge base',
        ].map((item) => (
          <Box key={item} display="flex" alignItems="center" gap={1.5} mb={1.5}>
            <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#2563EB', flexShrink: 0 }} />
            <Typography variant="body1" color="#94A3B8">{item}</Typography>
          </Box>
        ))}
      </Box>

      {/* Right login form */}
      <Box
        sx={{
          width: { xs: '100%', md: 480 },
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          px: 4,
          bgcolor: '#F8FAFC',
        }}
      >
        <Box width="100%" maxWidth={380}>
          <Box display="flex" alignItems="center" gap={1.5} mb={4}>
            <Box
              sx={{
                width: 40, height: 40, borderRadius: 2,
                bgcolor: '#1E3A8A', display: 'flex',
                alignItems: 'center', justifyContent: 'center',
              }}
            >
              <LockOutlinedIcon sx={{ color: '#fff', fontSize: 20 }} />
            </Box>
            <Box>
              <Typography variant="h3" color="text.primary">Sign In</Typography>
              <Typography variant="caption" color="text.secondary">
                Company IT Support Portal
              </Typography>
            </Box>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => dispatch(clearError())}>
              {error}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
            <TextField
              fullWidth
              label="Email Address"
              type="email"
              autoComplete="email"
              sx={{ mb: 2 }}
              {...register('email', {
                required: 'Email is required',
                pattern: { value: /^\S+@\S+\.\S+$/, message: 'Invalid email address' },
              })}
              error={!!errors.email}
              helperText={errors.email?.message}
            />
            <TextField
              fullWidth
              label="Password"
              type="password"
              autoComplete="current-password"
              sx={{ mb: 1 }}
              {...register('password', { required: 'Password is required', minLength: { value: 4, message: 'Minimum 4 characters' } })}
              error={!!errors.password}
              helperText={errors.password?.message}
            />
            <FormControlLabel
              control={<Checkbox size="small" {...register('rememberMe')} />}
              label={<Typography variant="body2" color="text.secondary">Remember me</Typography>}
              sx={{ mb: 2.5 }}
            />
            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={loading}
              sx={{ py: 1.25, fontWeight: 600 }}
            >
              {loading ? <CircularProgress size={20} color="inherit" /> : 'Sign In'}
            </Button>
          </Box>

          <Typography variant="caption" color="text.secondary" display="block" textAlign="center" mt={3}>
            Use your company email and password to sign in
          </Typography>
        </Box>
      </Box>
    </Box>
  )
}
