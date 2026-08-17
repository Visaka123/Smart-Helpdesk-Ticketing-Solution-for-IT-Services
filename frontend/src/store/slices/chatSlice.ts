import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import type { ChatMessage } from '../../types'
import { chatbotApi } from '../../api/services'

function genId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

interface ChatState {
  messages: ChatMessage[]
  loading: boolean
  error: string | null
}

const initialState: ChatState = {
  messages: [],
  loading: false,
  error: null,
}

export const sendMessage = createAsyncThunk(
  'chatbot/send',
  async (message: string, { rejectWithValue }) => {
    try {
      const res = await chatbotApi.ask(message)
      return res.data
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.detail || 'Failed to get response')
    }
  }
)

const chatSlice = createSlice({
  name: 'chatbot',
  initialState,
  reducers: {
    addUserMessage(state, action: PayloadAction<string>) {
      state.messages.push({
        id: genId(),
        role: 'user',
        content: action.payload,
        timestamp: new Date(),
      })
    },
    setMessages(state, action: PayloadAction<ChatMessage[]>) {
      state.messages = action.payload
      state.error = null
    },
    clearConversation(state) {
      state.messages = []
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(sendMessage.pending, (state) => { state.loading = true; state.error = null })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.loading = false
        state.messages.push({
          id: genId(),
          role: 'assistant',
          content: action.payload.answer || 'Unable to search the knowledge base. Please try again.',
          timestamp: new Date(),
          sources: action.payload.sources || [],
          similar_tickets: action.payload.similar_tickets,
          confidence: action.payload.confidence,
          suggested_actions: action.payload.suggested_actions,
          error: action.payload.error,
        })
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload as string
        state.messages.push({
          id: genId(),
          role: 'assistant',
          content: 'Unable to search the knowledge base. Please try again.',
          timestamp: new Date(),
          sources: [],
          error: true,
        })
      })
  },
})

export const { addUserMessage, setMessages, clearConversation } = chatSlice.actions
export default chatSlice.reducer
