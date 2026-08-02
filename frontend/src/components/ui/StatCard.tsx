import { Card, CardContent, Typography, Box, SvgIconProps } from '@mui/material'
import type { ElementType } from 'react'

interface StatCardProps {
  title: string
  value: number | string
  icon: ElementType<SvgIconProps>
  color?: string
  subtitle?: string
}

export default function StatCard({ title, value, icon: Icon, color = '#1E3A8A', subtitle }: StatCardProps) {
  return (
    <Card>
      <CardContent sx={{ p: 2.5 }}>
        <Box display="flex" alignItems="flex-start" justifyContent="space-between">
          <Box>
            <Typography variant="caption" color="text.secondary" fontWeight={500} textTransform="uppercase" letterSpacing="0.05em">
              {title}
            </Typography>
            <Typography variant="h3" fontWeight={700} mt={0.5} color="text.primary">
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="caption" color="text.secondary" mt={0.5} display="block">
                {subtitle}
              </Typography>
            )}
          </Box>
          <Box
            sx={{
              width: 44,
              height: 44,
              borderRadius: 2,
              backgroundColor: `${color}14`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Icon sx={{ color, fontSize: 22 }} />
          </Box>
        </Box>
      </CardContent>
    </Card>
  )
}
