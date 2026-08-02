import { Box, Typography, Divider } from '@mui/material'
import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  subtitle?: string
  action?: ReactNode
}

export default function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <Box mb={3}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={1.5}>
        <Box>
          <Typography variant="h2" color="text.primary">{title}</Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" mt={0.25}>{subtitle}</Typography>
          )}
        </Box>
        {action && <Box>{action}</Box>}
      </Box>
      <Divider />
    </Box>
  )
}
