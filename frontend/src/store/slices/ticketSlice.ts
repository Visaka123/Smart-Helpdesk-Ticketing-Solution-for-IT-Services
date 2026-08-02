import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import type { Ticket, TicketStats, CreateTicketPayload } from '../../types'
import { ticketApi } from '../../api/services'

interface TicketState {
  tickets: Ticket[]
  stats: TicketStats | null
  loading: boolean
  error: string | null
  createResult: any | null
}

const initialState: TicketState = {
  tickets: [],
  stats: null,
  loading: false,
  error: null,
  createResult: null,
}

export const fetchTickets = createAsyncThunk('tickets/fetchAll', async (_, { rejectWithValue }) => {
  try {
    const res = await ticketApi.getAll()
    return res.data
  } catch (err: any) {
    return rejectWithValue(err.response?.data?.detail || 'Failed to fetch tickets')
  }
})

export const fetchStats = createAsyncThunk('tickets/fetchStats', async (_, { rejectWithValue }) => {
  try {
    const res = await ticketApi.getStats()
    return res.data
  } catch (err: any) {
    return rejectWithValue(err.response?.data?.detail || 'Failed to fetch stats')
  }
})

export const createTicket = createAsyncThunk(
  'tickets/create',
  async (payload: CreateTicketPayload, { rejectWithValue }) => {
    try {
      const res = await ticketApi.create(payload)
      return res.data
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.detail || 'Failed to create ticket')
    }
  }
)

const ticketSlice = createSlice({
  name: 'tickets',
  initialState,
  reducers: {
    clearCreateResult(state) {
      state.createResult = null
    },
    clearError(state) {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchTickets.pending, (state) => { state.loading = true; state.error = null })
      .addCase(fetchTickets.fulfilled, (state, action) => { state.loading = false; state.tickets = action.payload })
      .addCase(fetchTickets.rejected, (state, action) => { state.loading = false; state.error = action.payload as string })
      .addCase(fetchStats.pending, (state) => { state.loading = true })
      .addCase(fetchStats.fulfilled, (state, action) => { state.loading = false; state.stats = action.payload })
      .addCase(fetchStats.rejected, (state, action) => { state.loading = false; state.error = action.payload as string })
      .addCase(createTicket.pending, (state) => { state.loading = true; state.error = null })
      .addCase(createTicket.fulfilled, (state, action) => { state.loading = false; state.createResult = action.payload })
      .addCase(createTicket.rejected, (state, action) => { state.loading = false; state.error = action.payload as string })
  },
})

export const { clearCreateResult, clearError } = ticketSlice.actions
export default ticketSlice.reducer
