import React, { useState, useEffect } from 'react'
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Grid,
  Chip,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  Divider,
  useTheme,
  Stack,
  Checkbox,
  FormControlLabel,
  Snackbar,
  IconButton,
  Collapse,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import CancelIcon from '@mui/icons-material/Cancel'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import LockIcon from '@mui/icons-material/Lock'
import GroupIcon from '@mui/icons-material/Group'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import CloseIcon from '@mui/icons-material/Close'
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ThumbDownAltOutlinedIcon from '@mui/icons-material/ThumbDownAltOutlined'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp'
import CloudUploadOutlinedIcon from '@mui/icons-material/CloudUploadOutlined'
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined'
import PictureAsPdfOutlinedIcon from '@mui/icons-material/PictureAsPdfOutlined'
import ImageOutlinedIcon from '@mui/icons-material/ImageOutlined'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { fixesApi, attachmentApi } from '../api/services'
import type { SuggestedFix, TicketAttachment } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export default function CreateTicketPage() {
  const navigate = useNavigate()
  const theme = useTheme()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [department, setDepartment] = useState('Finance')
  const [requesterName, setRequesterName] = useState('Alice Employee')
  const [submitting, setSubmitting] = useState(false)

  // Interstitial Modal State
  const [interstitialOpen, setInterstitialOpen] = useState(false)
  const [interstitialMatch, setInterstitialMatch] = useState<any>(null)
  const [interstitialType, setInterstitialType] = useState<'open' | 'in_progress' | 'resolved' | null>(null)
  const [inlineMatch, setInlineMatch] = useState<any>(null)

  // Toast Notification State
  const [toastOpen, setToastOpen] = useState(false)
  const [toastMessage, setToastMessage] = useState('')

  // Hard Block Modal State
  const [blockDialogOpen, setBlockDialogOpen] = useState(false)
  const [blockData, setBlockData] = useState<any>(null)

  // Ticket Created Confirmation Modal
  const [successDialogOpen, setSuccessDialogOpen] = useState(false)
  const [createdTicket, setCreatedTicket] = useState<any>(null)

  // Document Attachment State
  const [attachedFiles, setAttachedFiles] = useState<File[]>([])
  const [fileError, setFileError] = useState<string | null>(null)
  const [uploadingFiles, setUploadingFiles] = useState<boolean>(false)
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const fileInputRef = React.useRef<HTMLInputElement | null>(null)

  const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024 // 15MB
  const FORBIDDEN_EXTENSIONS = ['.exe', '.bat', '.cmd', '.sh', '.msi', '.vbs', '.js', '.bin', '.com', '.scr', '.pif']

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase()
    if (ext === 'pdf') {
      return <PictureAsPdfOutlinedIcon sx={{ color: '#DC2626', fontSize: 22 }} />
    }
    if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext || '')) {
      return <ImageOutlinedIcon sx={{ color: '#2563EB', fontSize: 22 }} />
    }
    return <InsertDriveFileOutlinedIcon sx={{ color: '#4B5563', fontSize: 22 }} />
  }

  const handleAddFiles = (newFiles: FileList | File[]) => {
    setFileError(null)
    const validFiles: File[] = []
    const existingNames = new Set(attachedFiles.map((f) => f.name.toLowerCase()))

    for (let i = 0; i < newFiles.length; i++) {
      const file = newFiles[i]
      const ext = '.' + (file.name.split('.').pop()?.toLowerCase() || '')

      if (FORBIDDEN_EXTENSIONS.includes(ext)) {
        setFileError(`File "${file.name}" has a restricted format (${ext}). Executable scripts cannot be uploaded.`)
        continue
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        setFileError(`File "${file.name}" (${formatFileSize(file.size)}) exceeds the 15MB size limit.`)
        continue
      }

      if (existingNames.has(file.name.toLowerCase())) {
        continue
      }

      validFiles.push(file)
      existingNames.add(file.name.toLowerCase())
    }

    if (validFiles.length > 0) {
      setAttachedFiles((prev) => [...prev, ...validFiles])
    }
  }

  const handleRemoveFile = (indexToRemove: number) => {
    setAttachedFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove))
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleAddFiles(e.dataTransfer.files)
    }
  }

  // Fix suggestions state ("Fixes that worked before")
  const [suggestions, setSuggestions] = useState<SuggestedFix[]>([])
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [solvedMessage, setSolvedMessage] = useState<string | null>(null)
  const [dismissedSuggestionIds, setDismissedSuggestionIds] = useState<number[]>([])
  const [expandedSummaryIds, setExpandedSummaryIds] = useState<Record<number, boolean>>({})

  // Debounced fetch for suggestions: 5+ words in title OR 20+ chars in description, 800ms wait
  useEffect(() => {
    const wordCount = title.trim() ? title.trim().split(/\s+/).length : 0
    const charCount = description.trim().length

    if (wordCount < 5 && charCount < 20) {
      setSuggestions([])
      return
    }

    const timer = setTimeout(async () => {
      if (interstitialOpen) return

      try {
        setLoadingSuggestions(true)
        const res = await fixesApi.suggestFixes(title, description, department)
        if (Array.isArray(res.data)) {
          setSuggestions(res.data)
        } else {
          setSuggestions([])
        }
      } catch (err) {
        console.warn('Error fetching fix suggestions:', err)
        setSuggestions([])
      } finally {
        setLoadingSuggestions(false)
      }
    }, 800)

    return () => clearTimeout(timer)
  }, [title, description, department, interstitialOpen])

  const handleSolved = async (s: SuggestedFix) => {
    try {
      await fixesApi.recordFeedback({
        suggestion_ticket_id: s.ticket_id,
        action: 'solved',
        relevance: s.relevance,
        query_text: `${title} ${description}`,
      })
    } catch (e) {
      console.warn('Feedback error:', e)
    }
    setSolvedMessage(`Thank you! Ticket #${s.ticket_id} marked as solving your issue. No new ticket was submitted.`)
    setSuggestions([])
  }

  const handleNotHelpful = async (s: SuggestedFix) => {
    try {
      await fixesApi.recordFeedback({
        suggestion_ticket_id: s.ticket_id,
        action: 'not_helpful',
        relevance: s.relevance,
        query_text: `${title} ${description}`,
      })
    } catch (e) {
      console.warn('Feedback error:', e)
    }
    setDismissedSuggestionIds((prev) => [...prev, s.ticket_id])
  }

  const toggleExpand = (id: number) => {
    setExpandedSummaryIds((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const handleFollowTicket = async () => {
    if (!interstitialMatch) return
    const ticketId = interstitialMatch.ticket_id
    try {
      const token = localStorage.getItem('token')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`

      await axios.post(`${API_BASE}/ticket/${ticketId}/follow`, {
        requester_name: requesterName,
        requester_department: department,
        similarity_score: interstitialMatch.relevance_score || interstitialMatch.semantic_score || 0.0,
        new_ticket_text: `${title} ${description}`,
      }, { headers })

      setInterstitialOpen(false)
      setToastMessage(`You will get updates on #${ticketId}`)
      setToastOpen(true)
    } catch (err) {
      console.error('Error following ticket:', err)
      setToastMessage(`You will get updates on #${ticketId}`)
      setToastOpen(true)
      setInterstitialOpen(false)
    }
  }

  const handleSubmitMine = async () => {
    if (interstitialMatch) {
      try {
        await axios.post(`${API_BASE}/ticket/log-duplicate-decision`, {
          ticket_text: `${title} ${description}`,
          matched_ticket_id: interstitialMatch.ticket_id,
          similarity_score: interstitialMatch.relevance_score || interstitialMatch.semantic_score || 0.0,
          decision: 'submitted_anyway',
        })
      } catch (e) {
        console.warn('Telemetry log error:', e)
      }
    }
    setInterstitialOpen(false)
    await executeCreateTicket(true)
  }

  const handleDismissModal = async () => {
    if (interstitialMatch) {
      try {
        await axios.post(`${API_BASE}/ticket/log-duplicate-decision`, {
          ticket_text: `${title} ${description}`,
          matched_ticket_id: interstitialMatch.ticket_id,
          similarity_score: interstitialMatch.relevance_score || interstitialMatch.semantic_score || 0.0,
          decision: 'dismissed',
        })
      } catch (e) {
        console.warn('Telemetry log error:', e)
      }
    }
    setInterstitialOpen(false)
    // Preserves form data intact (title, description, etc. are untouched)
  }

  const executeCreateTicket = async (forceSkipCheck = false) => {
    setSubmitting(true)
    try {
      const token = localStorage.getItem('token')
      const storedUser = localStorage.getItem('user')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (storedUser) {
        try {
          const u = JSON.parse(storedUser)
          headers['X-User-Id'] = String(u.id)
          headers['X-User-Role'] = u.role || 'employee'
          headers['X-User-Email'] = u.email
          headers['X-User-Name'] = u.name
        } catch (e) {}
      }

      const suggestionsTried = suggestions.map((s) => ({
        ticket_id: s.ticket_id,
        title: s.title,
        relevance: s.relevance,
      }))

      const res = await axios.post(`${API_BASE}/ticket/create`, {
        title,
        description,
        requester_name: requesterName,
        requester_department: department,
        skip_duplicate_check: forceSkipCheck,
        suggestions_tried: suggestionsTried.length > 0 ? suggestionsTried : undefined,
      }, { headers })

      if (res.data.is_hard_blocked) {
        setBlockData(res.data)
        setBlockDialogOpen(true)
        setSubmitting(false)
        return
      }

      const created = res.data.ticket || res.data
      const newTicketId = created.id

      // Upload any attached documents
      if (newTicketId && attachedFiles.length > 0) {
        setUploadingFiles(true)
        try {
          const uploadRes = await attachmentApi.upload(newTicketId, attachedFiles)
          if (uploadRes.data?.attachments) {
            created.attachments = uploadRes.data.attachments
          }
        } catch (uploadErr) {
          console.error('Error uploading attachments:', uploadErr)
        } finally {
          setUploadingFiles(false)
        }
      }

      setCreatedTicket(created)
      setSuccessDialogOpen(true)
      setAttachedFiles([])
    } catch (err) {
      console.error('Error submitting ticket:', err)
      alert('Failed to submit ticket. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !description.trim()) {
      alert('Please enter both ticket title and description.')
      return
    }

    setSubmitting(true)
    try {
      const token = localStorage.getItem('token')
      const storedUser = localStorage.getItem('user')
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      if (storedUser) {
        try {
          const u = JSON.parse(storedUser)
          headers['X-User-Id'] = String(u.id)
          headers['X-User-Role'] = u.role || 'employee'
          headers['X-User-Email'] = u.email
          headers['X-User-Name'] = u.name
        } catch (e) {}
      }

      // 1. Run Pre-Submission Duplicate Check using backend similarity matcher
      const dupRes = await axios.post(`${API_BASE}/ticket/check-duplicate`, {
        title,
        description,
      }, { headers })

      const data = dupRes.data
      if (data && data.should_show_modal && data.top_match) {
        const match = data.top_match
        setInterstitialMatch(match)
        if (match.status === 'resolved' || match.status === 'closed') {
          setInterstitialType('resolved')
        } else if (match.status === 'in_progress') {
          setInterstitialType('in_progress')
        } else {
          setInterstitialType('open')
        }
        setInterstitialOpen(true)
        setSubmitting(false)
        return
      }

      if (data && data.should_show_inline_hint && (data.inline_match || data.top_match)) {
        setInlineMatch(data.inline_match || data.top_match)
      } else {
        setInlineMatch(null)
      }

      // No match above threshold -> submit immediately
      await executeCreateTicket(false)
    } catch (err) {
      console.error('Error checking duplicate ticket:', err)
      await executeCreateTicket(false)
    }
  }

  return (
    <Box maxWidth={720} mx="auto" py={3}>
      <Paper
        elevation={0}
        sx={{
          p: 4,
          bgcolor: 'background.paper',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 3,
          boxShadow: theme.palette.mode === 'light' ? '0 4px 20px rgba(0, 0, 0, 0.05)' : 'none',
        }}
      >
        <Box mb={3.5}>
          <Typography variant="h4" fontWeight={800} color="text.primary" gutterBottom>
            Create Support Ticket
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Submit an IT service request or report an issue. Your ticket will be automatically classified and routed to the appropriate support team.
          </Typography>
        </Box>

        <form onSubmit={handleSubmit}>
          <Stack spacing={3}>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <TextField
                  label="Requester Name"
                  fullWidth
                  required
                  value={requesterName}
                  onChange={(e) => setRequesterName(e.target.value)}
                  placeholder="e.g. Alice Employee"
                  variant="outlined"
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  select
                  label="Department"
                  fullWidth
                  required
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  SelectProps={{ native: true }}
                  variant="outlined"
                >
                  <option value="Finance">Finance</option>
                  <option value="Sales">Sales</option>
                  <option value="Engineering">Engineering</option>
                  <option value="Human Resources">Human Resources</option>
                </TextField>
              </Grid>
            </Grid>

            <TextField
              label="Ticket Title"
              fullWidth
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Unable to access financial reporting portal"
              variant="outlined"
            />

            <TextField
              label="Detailed Description"
              fullWidth
              required
              multiline
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Please provide details about the issue, including error messages, steps to reproduce, or impacted systems..."
              variant="outlined"
            />

            {/* Supporting Documents & Attachments Section */}
            <Box>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                <Box display="flex" alignItems="center" gap={1}>
                  <AttachFileIcon sx={{ color: 'primary.main', fontSize: 20 }} />
                  <Typography variant="subtitle2" fontWeight={700} color="text.primary">
                    Attach Documents & Screenshots
                  </Typography>
                </Box>
                <Typography variant="caption" color="text.secondary">
                  Optional • PDF, Word, Excel, Logs, PNG, JPG (up to 15MB each)
                </Typography>
              </Box>

              {/* Hidden File Input */}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    handleAddFiles(e.target.files)
                    e.target.value = ''
                  }
                }}
              />

              {/* Drag & Drop Upload Zone */}
              <Paper
                variant="outlined"
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                sx={{
                  p: 2.5,
                  textAlign: 'center',
                  borderStyle: 'dashed',
                  borderWidth: 2,
                  borderColor: isDragging ? theme.palette.primary.main : theme.palette.divider,
                  bgcolor: isDragging
                    ? theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B'
                    : theme.palette.mode === 'light' ? '#F8FAFC' : '#0B132B',
                  borderRadius: 2,
                  cursor: 'pointer',
                  transition: 'all 0.2s ease-in-out',
                  '&:hover': {
                    borderColor: theme.palette.primary.main,
                    bgcolor: theme.palette.mode === 'light' ? '#F1F5F9' : '#1E293B',
                  },
                }}
              >
                <CloudUploadOutlinedIcon sx={{ fontSize: 34, color: 'primary.main', mb: 0.5 }} />
                <Typography variant="body2" fontWeight={700} color="text.primary">
                  Click to browse or drag and drop files here
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                  Attach screenshots, error logs, or relevant documents to expedite ticket resolution
                </Typography>
              </Paper>

              {/* File Error Alert */}
              {fileError && (
                <Alert severity="error" onClose={() => setFileError(null)} sx={{ mt: 1.5, borderRadius: 2 }}>
                  {fileError}
                </Alert>
              )}

              {/* Selected Files List */}
              {attachedFiles.length > 0 && (
                <Box mt={1.5}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                      Files to Attach ({attachedFiles.length})
                    </Typography>
                    <Button
                      size="small"
                      color="inherit"
                      onClick={() => setAttachedFiles([])}
                      sx={{ fontSize: '0.72rem', textTransform: 'none', py: 0 }}
                    >
                      Clear all
                    </Button>
                  </Box>
                  <Stack spacing={1}>
                    {attachedFiles.map((file, idx) => (
                      <Paper
                        key={`${file.name}-${idx}`}
                        elevation={0}
                        sx={{
                          p: 1.2,
                          px: 1.8,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          borderRadius: 2,
                          border: `1px solid ${theme.palette.divider}`,
                          bgcolor: theme.palette.mode === 'light' ? '#FFFFFF' : '#1E293B',
                        }}
                      >
                        <Box display="flex" alignItems="center" gap={1.5} sx={{ minWidth: 0, overflow: 'hidden' }}>
                          {getFileIcon(file.name)}
                          <Box sx={{ minWidth: 0 }}>
                            <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: { xs: 200, sm: 380 } }}>
                              {file.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {formatFileSize(file.size)}
                            </Typography>
                          </Box>
                        </Box>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleRemoveFile(idx)
                          }}
                          aria-label="remove attachment"
                        >
                          <CloseIcon fontSize="small" />
                        </IconButton>
                      </Paper>
                    ))}
                  </Stack>
                </Box>
              )}
            </Box>

            {inlineMatch && (
              <Alert severity="info" sx={{ borderRadius: 2 }}>
                Possibly related: #{inlineMatch.ticket_id} ({inlineMatch.title})
              </Alert>
            )}

            {/* Solved Deflection Notice */}
            {solvedMessage && (
              <Alert
                severity="success"
                icon={<CheckCircleIcon fontSize="inherit" />}
                action={
                  <IconButton size="small" aria-label="close" color="inherit" onClick={() => setSolvedMessage(null)}>
                    <CloseIcon fontSize="small" />
                  </IconButton>
                }
                sx={{ borderRadius: 2 }}
              >
                {solvedMessage}
              </Alert>
            )}

            {/* Fixes that worked before (Recommended similar resolved tickets) */}
            {!interstitialOpen && suggestions.filter((s) => !dismissedSuggestionIds.includes(s.ticket_id)).length > 0 && (
              <Card
                variant="outlined"
                sx={{
                  bgcolor: theme.palette.mode === 'light' ? '#F0FDF4' : '#062012',
                  borderColor: theme.palette.mode === 'light' ? '#BBF7D0' : '#166534',
                  borderRadius: 2,
                }}
              >
                <CardContent sx={{ pb: '16px !important' }}>
                  <Box display="flex" alignItems="center" gap={1} mb={1.5}>
                    <LightbulbOutlinedIcon sx={{ color: '#16A34A', fontSize: 22 }} />
                    <Typography variant="subtitle1" fontWeight={700} sx={{ color: theme.palette.mode === 'light' ? '#15803D' : '#4ADE80' }}>
                      Fixes that worked before
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', ml: 'auto' }}>
                      Similar resolved issues
                    </Typography>
                  </Box>

                  <Stack spacing={1.5}>
                    {suggestions
                      .filter((s) => !dismissedSuggestionIds.includes(s.ticket_id))
                      .slice(0, 3)
                      .map((s) => {
                        const isExpanded = Boolean(expandedSummaryIds[s.ticket_id])
                        const pct = Math.round(s.relevance * 100)
                        const isTruncated = s.resolution_summary.length > 130
                        const displaySummary = isExpanded || !isTruncated
                          ? s.resolution_summary
                          : s.resolution_summary.slice(0, 130) + '...'

                        return (
                          <Paper
                            key={s.ticket_id}
                            elevation={0}
                            sx={{
                              p: 2,
                              borderRadius: 2,
                              border: `1px solid ${theme.palette.divider}`,
                              bgcolor: 'background.paper',
                            }}
                          >
                            <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={1} mb={1}>
                              <Box>
                                <Typography variant="body2" fontWeight={700} color="text.primary">
                                  #{s.ticket_id} — {s.title}
                                </Typography>
                                <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                                  <Chip label={s.category || 'General IT'} size="small" variant="outlined" sx={{ height: 20, fontSize: '0.7rem' }} />
                                  {s.resolved_at && (
                                    <Typography variant="caption" color="text.secondary">
                                      Resolved {new Date(s.resolved_at).toLocaleDateString()}
                                    </Typography>
                                  )}
                                </Box>
                              </Box>
                              <Chip
                                label={`${pct}% Match`}
                                size="small"
                                sx={{
                                  height: 22,
                                  fontWeight: 700,
                                  fontSize: '0.72rem',
                                  bgcolor: pct >= 80 ? '#DCFCE7' : '#FEF3C7',
                                  color: pct >= 80 ? '#15803D' : '#92400E',
                                }}
                              />
                            </Box>

                            <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic', mb: 1.5, lineHeight: 1.5 }}>
                              {displaySummary}
                              {isTruncated && (
                                <Button
                                  size="small"
                                  onClick={() => toggleExpand(s.ticket_id)}
                                  sx={{ p: 0, minWidth: 'auto', ml: 1, textTransform: 'none', fontWeight: 600, fontSize: '0.75rem' }}
                                >
                                  {isExpanded ? 'Show less' : 'Read more'}
                                </Button>
                              )}
                            </Typography>

                            <Box display="flex" justifyContent="flex-end" alignItems="center" gap={1}>
                              <Button
                                size="small"
                                variant="outlined"
                                color="inherit"
                                onClick={() => handleNotHelpful(s)}
                                startIcon={<ThumbDownAltOutlinedIcon sx={{ fontSize: 15 }} />}
                                sx={{ textTransform: 'none', fontSize: '0.75rem', px: 1.5, py: 0.5 }}
                              >
                                Not helpful
                              </Button>
                              <Button
                                size="small"
                                variant="contained"
                                onClick={() => handleSolved(s)}
                                startIcon={<CheckCircleIcon sx={{ fontSize: 16 }} />}
                                sx={{
                                  textTransform: 'none',
                                  fontSize: '0.75rem',
                                  px: 2,
                                  py: 0.5,
                                  bgcolor: '#16A34A',
                                  '&:hover': { bgcolor: '#15803D' },
                                }}
                              >
                                This solved it
                              </Button>
                            </Box>
                          </Paper>
                        )
                      })}
                  </Stack>
                </CardContent>
              </Card>
            )}

            <Divider sx={{ my: 1 }} />

            <Box display="flex" justifyContent="flex-end" alignItems="center" gap={2}>
              <Button
                variant="outlined"
                color="inherit"
                onClick={() => navigate('/tickets')}
                startIcon={<CancelIcon />}
                disabled={submitting || uploadingFiles}
                sx={{ px: 3, py: 1, fontWeight: 700 }}
              >
                Cancel
              </Button>
                <Button
                  type="submit"
                  variant="contained"
                  disabled={submitting || uploadingFiles}
                  startIcon={<SendIcon />}
                  sx={{
                    px: 4,
                    py: 1,
                    fontWeight: 700,
                    bgcolor: '#2563EB',
                    '&:hover': { bgcolor: '#1D4ED8' },
                  }}
                >
                  {uploadingFiles ? 'Uploading Attachments...' : submitting ? 'Submitting...' : 'Submit Ticket'}
                </Button>
            </Box>
          </Stack>
        </form>
      </Paper>

      {/* COMPACT PROFESSIONAL CREATION SUCCESS DIALOG */}
      {createdTicket && (
        <Dialog
          open={successDialogOpen}
          onClose={() => setSuccessDialogOpen(false)}
          maxWidth="xs"
          fullWidth
          PaperProps={{
            sx: { borderRadius: 3, p: 1 },
          }}
        >
          <DialogTitle sx={{ pb: 1, display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <CheckCircleOutlineIcon sx={{ color: '#10B981', fontSize: 32 }} />
            <Box>
              <Typography variant="h6" fontWeight={800} color="text.primary">
                Ticket Created Successfully
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Ticket ID: #{createdTicket.id}
              </Typography>
            </Box>
          </DialogTitle>

          <DialogContent sx={{ py: 2 }}>
            <Paper
              variant="outlined"
              sx={{ p: 2.5, bgcolor: theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A', borderRadius: 2 }}
            >
              <Stack spacing={1.8}>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" color="text.secondary" fontWeight={600}>
                    Category
                  </Typography>
                  <Typography variant="body2" fontWeight={800} color="primary.main">
                    {createdTicket.category || createdTicket.predicted_category || 'Hardware'}
                  </Typography>
                </Box>

                <Divider light />

                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" color="text.secondary" fontWeight={600}>
                    Assigned Team
                  </Typography>
                  <Typography variant="body2" fontWeight={800} color="text.primary">
                    {createdTicket.assigned_team || createdTicket.predicted_team || 'General Support'}
                  </Typography>
                </Box>

                <Divider light />

                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" color="text.secondary" fontWeight={600}>
                    Assigned Agent
                  </Typography>
                  <Typography variant="body2" fontWeight={800} color="text.primary">
                    {createdTicket.assigned_agent_name ? `Assigned to ${createdTicket.assigned_agent_name}` : 'Unassigned / Queued'}
                  </Typography>
                </Box>

                {createdTicket.assignment_reason && (
                  <Box sx={{ mt: -0.5, p: 1.2, bgcolor: theme.palette.mode === 'light' ? '#EEF2F6' : '#1E293B', borderRadius: 1.5 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontStyle: 'italic', wordBreak: 'break-word' }}>
                      {createdTicket.assignment_reason}
                    </Typography>
                  </Box>
                )}

                <Divider light />

                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" color="text.secondary" fontWeight={600}>
                    Priority
                  </Typography>
                  <Chip
                    label={createdTicket.priority || 'Medium'}
                    size="small"
                    color={
                      createdTicket.priority === 'Critical'
                        ? 'error'
                        : createdTicket.priority === 'High'
                        ? 'warning'
                        : 'primary'
                    }
                    sx={{ fontWeight: 800, height: 24 }}
                  />
                </Box>

                <Divider light />

                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" color="text.secondary" fontWeight={600}>
                    SLA Target
                  </Typography>
                  <Box display="flex" alignItems="center" gap={0.5}>
                    <AccessTimeIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                    <Typography variant="body2" fontWeight={800} color="text.primary">
                      {createdTicket.sla_hours ? `${createdTicket.sla_hours} hours` : '24 hours'}
                    </Typography>
                  </Box>
                </Box>

                {createdTicket.attachments && createdTicket.attachments.length > 0 && (
                  <>
                    <Divider light />
                    <Box>
                      <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
                        <Typography variant="body2" color="text.secondary" fontWeight={600}>
                          Attached Documents
                        </Typography>
                        <Chip
                          label={`${createdTicket.attachments.length} attached`}
                          size="small"
                          color="info"
                          sx={{ fontWeight: 700, height: 22 }}
                        />
                      </Box>
                      <Stack spacing={0.5} mt={0.5}>
                        {createdTicket.attachments.map((att: any) => (
                          <Typography
                            key={att.id || att.filename}
                            variant="caption"
                            color="text.primary"
                            sx={{ display: 'flex', alignItems: 'center', gap: 0.5, wordBreak: 'break-all' }}
                          >
                            • {att.filename} ({att.formatted_size || `${(att.file_size / 1024).toFixed(1)} KB`})
                          </Typography>
                        ))}
                      </Stack>
                    </Box>
                  </>
                )}
              </Stack>
            </Paper>
          </DialogContent>

          <DialogActions sx={{ p: 2, pt: 1 }}>
            <Button
              variant="contained"
              fullWidth
              onClick={() => {
                setSuccessDialogOpen(false)
                navigate('/dashboard')
              }}
              sx={{ bgcolor: '#2563EB', fontWeight: 700, py: 1 }}
            >
              Return to Dashboard
            </Button>
          </DialogActions>
        </Dialog>
      )}

      {/* PRE-SUBMISSION SIMILARITY INTERSTITIAL DIALOG */}
      {interstitialMatch && (
        <Dialog
          open={interstitialOpen}
          onClose={handleDismissModal}
          maxWidth="sm"
          fullWidth
          PaperProps={{ sx: { borderRadius: 3 } }}
        >
          <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
            <Box display="flex" alignItems="center" gap={1.5}>
              {interstitialType === 'resolved' ? (
                <CheckCircleOutlineIcon sx={{ color: '#059669', fontSize: 28 }} />
              ) : interstitialType === 'in_progress' ? (
                <GroupIcon sx={{ color: '#2563EB', fontSize: 28 }} />
              ) : (
                <AccessTimeIcon sx={{ color: '#D97706', fontSize: 28 }} />
              )}
              <Box>
                <Typography variant="h6" fontWeight={800} color="text.primary">
                  {interstitialType === 'resolved'
                    ? 'A similar issue was recently resolved'
                    : interstitialType === 'in_progress'
                    ? 'Already reported and being worked on'
                    : 'Already reported, waiting for an agent'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Matched against existing Ticket #{interstitialMatch.ticket_id} (Relevance:{' '}
                  {Math.round((interstitialMatch.relevance_score || interstitialMatch.semantic_score || 0.75) * 100)}%)
                </Typography>
              </Box>
            </Box>
            <IconButton onClick={handleDismissModal} size="small" sx={{ color: 'text.secondary' }}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </DialogTitle>

          <DialogContent sx={{ py: 2 }}>
            {interstitialType === 'resolved' ? (
              <Paper
                variant="outlined"
                sx={{
                  p: 2.5,
                  bgcolor: theme.palette.mode === 'light' ? '#ECFDF5' : '#064E3B',
                  borderColor: '#A7F3D0',
                  borderRadius: 2.5,
                }}
              >
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <CheckCircleOutlineIcon sx={{ color: '#059669', fontSize: 20 }} />
                  <Typography variant="subtitle2" fontWeight={800} sx={{ color: '#065F46' }}>
                    Verified Resolution for Ticket #{interstitialMatch.ticket_id}
                  </Typography>
                </Box>
                <Typography variant="body2" fontWeight={700} sx={{ color: '#047857', mb: 1 }}>
                  {interstitialMatch.title}
                </Typography>
                <Divider sx={{ my: 1.5, borderColor: '#A7F3D0' }} />
                <Typography variant="caption" fontWeight={800} sx={{ color: '#065F46', display: 'block', mb: 0.5 }}>
                  RECOMMENDED RESOLUTION SUMMARY:
                </Typography>
                <Typography variant="body2" sx={{ color: '#064E3B', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
                  {interstitialMatch.resolution_summary || 'Verified fix applied by operations.'}
                </Typography>
                {interstitialMatch.resolution_detail && (
                  <Typography variant="caption" sx={{ color: '#047857', display: 'block', mt: 1, fontStyle: 'italic' }}>
                    {interstitialMatch.resolution_detail}
                  </Typography>
                )}
              </Paper>
            ) : interstitialType === 'in_progress' ? (
              <Paper
                variant="outlined"
                sx={{
                  p: 2.5,
                  bgcolor: theme.palette.mode === 'light' ? '#EFF6FF' : '#1E293B',
                  borderColor: '#BFDBFE',
                  borderRadius: 2.5,
                }}
              >
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <GroupIcon sx={{ color: '#2563EB', fontSize: 20 }} />
                  <Typography variant="subtitle2" fontWeight={800} sx={{ color: '#1E40AF' }}>
                    Ticket #{interstitialMatch.ticket_id} — Being Worked On
                  </Typography>
                </Box>
                <Typography variant="body2" fontWeight={700} sx={{ color: '#1D4ED8', mb: 1 }}>
                  {interstitialMatch.title}
                </Typography>
                <Box display="flex" gap={1} my={1.5}>
                  <Chip
                    label="Status: IN PROGRESS"
                    size="small"
                    style={{ backgroundColor: '#DBEAFE', color: '#1E40AF', fontWeight: 800 }}
                  />
                  <Chip
                    label={`Team: ${interstitialMatch.assigned_team || 'IT Support'}`}
                    size="small"
                    style={{ backgroundColor: '#F1F5F9', color: '#334155', fontWeight: 800 }}
                  />
                  {interstitialMatch.assigned_agent_name && (
                    <Chip
                      label={`Agent: ${interstitialMatch.assigned_agent_name}`}
                      size="small"
                      style={{ backgroundColor: '#FEF3C7', color: '#B45309', fontWeight: 800 }}
                    />
                  )}
                </Box>
                <Typography variant="caption" color="text.secondary" display="block">
                  {interstitialMatch.description}
                </Typography>
                <Alert severity="info" icon={false} sx={{ mt: 1.5, py: 0.5, px: 1.5, fontSize: '0.78rem', borderRadius: 1.5 }}>
                  This incident was reported by another employee and is currently being worked on.
                </Alert>
              </Paper>
            ) : (
              <Paper
                variant="outlined"
                sx={{
                  p: 2.5,
                  bgcolor: theme.palette.mode === 'light' ? '#FFFBEB' : '#451A03',
                  borderColor: '#FDE68A',
                  borderRadius: 2.5,
                }}
              >
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <AccessTimeIcon sx={{ color: '#D97706', fontSize: 20 }} />
                  <Typography variant="subtitle2" fontWeight={800} sx={{ color: '#92400E' }}>
                    Ticket #{interstitialMatch.ticket_id} — Open in Queue
                  </Typography>
                </Box>
                <Typography variant="body2" fontWeight={700} sx={{ color: '#B45309', mb: 1 }}>
                  {interstitialMatch.title}
                </Typography>
                <Box display="flex" gap={1} my={1.5}>
                  <Chip
                    label="Status: OPEN"
                    size="small"
                    style={{ backgroundColor: '#FEF3C7', color: '#B45309', fontWeight: 800 }}
                  />
                  <Chip
                    label={`Team: ${interstitialMatch.assigned_team || 'IT Support'}`}
                    size="small"
                    style={{ backgroundColor: '#EFF6FF', color: '#2563EB', fontWeight: 800 }}
                  />
                </Box>
                <Typography variant="caption" color="text.secondary" display="block">
                  {interstitialMatch.description}
                </Typography>
                <Alert severity="warning" icon={false} sx={{ mt: 1.5, py: 0.5, px: 1.5, fontSize: '0.78rem', borderRadius: 1.5 }}>
                  This incident was already reported and is currently waiting in the queue for an available agent.
                </Alert>
              </Paper>
            )}
          </DialogContent>

          <DialogActions sx={{ p: 2.5, pt: 1, gap: 1.5, flexDirection: 'column' }}>
            <Button
              variant="contained"
              fullWidth
              onClick={handleFollowTicket}
              sx={{ bgcolor: '#2563EB', fontWeight: 800, py: 1.25 }}
            >
              Follow #{interstitialMatch.ticket_id}
            </Button>
            <Button
              variant="outlined"
              color="inherit"
              fullWidth
              onClick={handleSubmitMine}
              sx={{ fontWeight: 700, textTransform: 'none' }}
            >
              This is different, submit mine
            </Button>
            <Button
              variant="text"
              color="inherit"
              fullWidth
              onClick={handleDismissModal}
              sx={{ fontWeight: 600, textTransform: 'none', color: 'text.secondary' }}
            >
              Cancel
            </Button>
          </DialogActions>
        </Dialog>
      )}

      {/* HARD BLOCK DUPLICATE MODAL */}
      {blockData && (
        <Dialog open={blockDialogOpen} onClose={() => setBlockDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, color: blockData.block_type === 'open_ticket_linked' ? '#D97706' : '#10B981' }}>
            <LockIcon sx={{ color: blockData.block_type === 'open_ticket_linked' ? '#D97706' : '#10B981' }} />
            {blockData.block_type === 'open_ticket_linked' ? 'Duplicate Prevented — Linked to Open Incident' : 'Issue Already Resolved!'}
          </DialogTitle>
          <DialogContent>
            {blockData.block_type === 'open_ticket_linked' ? (
              <Box>
                <Alert severity="warning" icon={<GroupIcon fontSize="small" />} sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" fontWeight={800}>
                    {blockData.message}
                  </Typography>
                  <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                    No duplicate ticket was created. You have been added as a linked requester on Ticket #{blockData.ticket.id} (Total linked users: {blockData.ticket.requester_count}).
                  </Typography>
                </Alert>
              </Box>
            ) : (
              <Box>
                <Alert severity="success" icon={<CheckCircleOutlineIcon fontSize="small" />} sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" fontWeight={800}>
                    This issue was already resolved — Ticket #{blockData.ticket.id}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    {blockData.ticket.resolution_summary}
                  </Typography>
                </Alert>
              </Box>
            )}
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button
              variant="contained"
              fullWidth
              onClick={() => {
                setBlockDialogOpen(false)
                navigate('/dashboard')
              }}
              sx={{ bgcolor: '#2563EB', fontWeight: 700 }}
            >
              Return to Dashboard
            </Button>
          </DialogActions>
        </Dialog>
      )}

      {/* CONFIRMATION TOAST NOTIFICATION */}
      <Snackbar
        open={toastOpen}
        autoHideDuration={5000}
        onClose={() => setToastOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setToastOpen(false)} severity="success" sx={{ width: '100%', fontWeight: 700 }}>
          {toastMessage}
        </Alert>
      </Snackbar>
    </Box>
  )
}
