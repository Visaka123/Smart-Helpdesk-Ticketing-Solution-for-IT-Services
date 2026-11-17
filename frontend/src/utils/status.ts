/**
 * frontend/src/utils/status.ts
 *
 * Canonical status options and normalization helpers for tickets.
 */

export interface StatusOption {
  value: string
  label: string
}

export const STATUS_OPTIONS: StatusOption[] = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'pending_user', label: 'Pending User' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
]

/**
 * Normalizes legacy or mixed-case status values to canonical forms.
 * E.g., 'OPEN', 'Open', 'new', 'assigned' -> 'open'
 *       'In Progress', 'in-progress' -> 'in_progress'
 *       'on_hold', 'waiting' -> 'pending_user'
 */
export function normalizeStatus(rawStatus?: string | null): string {
  if (!rawStatus) return 'open'
  const trimmed = rawStatus.trim().toLowerCase()
  const cleaned = trimmed.replace(/[\s-]+/g, '_')

  if (cleaned === 'open' || cleaned === 'new' || cleaned === 'assigned' || cleaned === 'reopened') {
    return 'open'
  }
  if (cleaned === 'in_progress' || cleaned === 'inprogress' || cleaned === 'working') {
    return 'in_progress'
  }
  if (
    cleaned === 'pending_user' ||
    cleaned === 'pending' ||
    cleaned === 'on_hold' ||
    cleaned === 'onhold' ||
    cleaned === 'waiting' ||
    cleaned === 'waiting_for_user'
  ) {
    return 'pending_user'
  }
  if (cleaned === 'resolved') {
    return 'resolved'
  }
  if (cleaned === 'closed' || cleaned === 'cancelled') {
    return 'closed'
  }
  return cleaned
}

/**
 * Returns human-readable label for a status string.
 */
export function formatStatusLabel(statusVal?: string | null): string {
  const norm = normalizeStatus(statusVal)
  const found = STATUS_OPTIONS.find((opt) => opt.value === norm)
  if (found) return found.label
  if (!statusVal) return 'Open'
  return statusVal.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

/**
 * Returns list of status options, appending any unrecognized status
 * dynamically so the dropdown never displays a blank/empty field.
 */
export function getStatusOptions(currentVal?: string | null): StatusOption[] {
  const norm = normalizeStatus(currentVal)
  const exists = STATUS_OPTIONS.some((opt) => opt.value === norm)
  if (!exists && norm) {
    return [...STATUS_OPTIONS, { value: norm, label: formatStatusLabel(currentVal) }]
  }
  return STATUS_OPTIONS
}
