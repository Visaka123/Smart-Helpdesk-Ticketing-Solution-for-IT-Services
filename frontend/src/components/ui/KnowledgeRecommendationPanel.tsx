import React from 'react'
import { Box, Typography, Paper, Chip, Button, useTheme } from '@mui/material'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import DownloadIcon from '@mui/icons-material/Download'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import DescriptionIcon from '@mui/icons-material/Description'

interface RecommendedArticle {
  id: number
  title: string
  document_type: string
  category: string
  snippet: string
  source_file: string
  download_url: string
  relevance_pct: number
}

interface KnowledgeRecommendationPanelProps {
  articles: RecommendedArticle[]
  summary?: string
}

export function KnowledgeRecommendationPanel({ articles, summary }: KnowledgeRecommendationPanelProps) {
  const theme = useTheme()

  if (!articles || articles.length === 0) return null

  const getDocIcon = (type: string) => {
    if (type === 'PDF') return <PictureAsPdfIcon style={{ color: '#DC2626', fontSize: 16 }} />
    if (type === 'DOCX') return <DescriptionIcon style={{ color: '#2563EB', fontSize: 16 }} />
    if (type === 'RESOLVED_TICKET') return <CheckCircleIcon style={{ color: '#059669', fontSize: 16 }} />
    return <MenuBookIcon style={{ color: '#D97706', fontSize: 16 }} />
  }

  return (
    <Paper sx={{ p: 2.5, bgcolor: theme.palette.mode === 'light' ? '#F8FAFC' : '#0F172A', border: '1px solid #CBD5E1', borderRadius: 2, mb: 3 }}>
      <Box display="flex" alignItems="center" gap={1} mb={1.5}>
        <MenuBookIcon style={{ color: '#2563EB', fontSize: 22 }} />
        <Typography variant="h6" fontWeight={800} style={{ color: theme.palette.text.primary }}>
          Proactive Knowledge & Verified SOP Recommendations
        </Typography>
      </Box>

      {summary && (
        <Typography variant="body2" style={{ color: theme.palette.text.secondary, marginBottom: 16 }}>
          {summary}
        </Typography>
      )}

      <Box display="flex" flexDirection="column" gap={1.5}>
        {articles.map((art, idx) => (
          <Paper
            key={idx}
            sx={{
              p: 2,
              bgcolor: 'background.paper',
              border: `1px solid ${theme.palette.divider}`,
              borderRadius: 2,
              transition: 'all 0.2s ease',
              '&:hover': { borderColor: '#2563EB', boxShadow: '0 4px 12px rgba(0,0,0,0.06)' },
            }}
          >
            <Box display="flex" justifyContent="space-between" alignItems="flex-start">
              <Box display="flex" alignItems="center" gap={1}>
                {getDocIcon(art.document_type)}
                <Typography variant="subtitle2" fontWeight={700} style={{ color: theme.palette.text.primary }}>
                  {art.title}
                </Typography>
              </Box>
              <Chip
                label={`${art.relevance_pct || 85}% RELEVANCE`}
                size="small"
                style={{ backgroundColor: '#D1FAE5', color: '#059669', fontWeight: 800, fontSize: '0.68rem' }}
              />
            </Box>

            <Typography variant="body2" style={{ color: theme.palette.text.secondary, marginTop: 6, marginBottom: 12 }}>
              {art.snippet}
            </Typography>

            <Box display="flex" justifyContent="space-between" alignItems="center" pt={1} borderTop={`1px solid ${theme.palette.divider}`}>
              <Typography variant="caption" fontWeight={600} style={{ color: theme.palette.text.secondary }}>
                Source: {art.source_file || art.category}
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<DownloadIcon fontSize="small" />}
                href={art.download_url}
                target="_blank"
                style={{ borderRadius: 6, fontWeight: 700, fontSize: '0.75rem' }}
              >
                Download Document ({art.document_type || 'PDF'})
              </Button>
            </Box>
          </Paper>
        ))}
      </Box>
    </Paper>
  )
}
