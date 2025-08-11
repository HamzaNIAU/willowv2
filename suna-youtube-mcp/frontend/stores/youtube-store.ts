/**
 * YouTube Store for Zustand
 * Manages YouTube-related state across the application
 */

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

interface YouTubeChannel {
  id: string
  name: string
  custom_url?: string
  thumbnail_url?: string
  subscriber_count?: number
  view_count?: number
  video_count?: number
  capabilities?: {
    upload: boolean
    analytics: boolean
    management: boolean
    streaming: boolean
    monetization: boolean
  }
}

interface UploadSession {
  upload_id: string
  channel_id: string
  video_id?: string
  title: string
  status: 'pending' | 'uploading' | 'completed' | 'failed' | 'cancelled'
  progress: {
    percentage: number
    bytes_uploaded: number
    total_bytes: number
    formatted_uploaded: string
    formatted_total: string
  }
  timing?: {
    elapsed_seconds: number
    upload_speed_formatted: string
    estimated_time_remaining: number
  }
  error?: string
  created_at: Date
  completed_at?: Date
}

interface YouTubeStore {
  // State
  channels: YouTubeChannel[]
  currentChannel: YouTubeChannel | null
  uploads: Map<string, UploadSession>
  currentUploadId: string | null
  isAuthenticating: boolean
  isLoadingChannels: boolean
  error: string | null

  // Actions - Channels
  setChannels: (channels: YouTubeChannel[]) => void
  setChannel: (channel: YouTubeChannel) => void
  addChannel: (channel: YouTubeChannel) => void
  removeChannel: (channelId: string) => void
  clearChannel: () => void
  selectChannel: (channelId: string) => void

  // Actions - Uploads
  startUpload: (session: UploadSession) => void
  updateUploadProgress: (uploadId: string, progress: UploadSession['progress']) => void
  updateUploadStatus: (uploadId: string, status: UploadSession['status'], error?: string) => void
  completeUpload: (uploadId: string, videoId: string) => void
  cancelUpload: (uploadId: string) => void
  clearUpload: (uploadId: string) => void
  
  // Actions - UI State
  setAuthenticating: (isAuthenticating: boolean) => void
  setLoadingChannels: (isLoading: boolean) => void
  setError: (error: string | null) => void
  
  // Computed
  getCurrentUpload: () => UploadSession | undefined
  getUpload: (uploadId: string) => UploadSession | undefined
  hasChannels: () => boolean
  getActiveUploads: () => UploadSession[]
}

export const useYouTubeStore = create<YouTubeStore>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        channels: [],
        currentChannel: null,
        uploads: new Map(),
        currentUploadId: null,
        isAuthenticating: false,
        isLoadingChannels: false,
        error: null,

        // Channel actions
        setChannels: (channels) => 
          set({ 
            channels, 
            currentChannel: channels.length > 0 ? channels[0] : null 
          }),

        setChannel: (channel) =>
          set((state) => ({
            channels: state.channels.some(c => c.id === channel.id)
              ? state.channels.map(c => c.id === channel.id ? channel : c)
              : [...state.channels, channel],
            currentChannel: channel
          })),

        addChannel: (channel) =>
          set((state) => ({
            channels: [...state.channels, channel],
            currentChannel: state.currentChannel || channel
          })),

        removeChannel: (channelId) =>
          set((state) => ({
            channels: state.channels.filter(c => c.id !== channelId),
            currentChannel: state.currentChannel?.id === channelId 
              ? state.channels[0] || null 
              : state.currentChannel
          })),

        clearChannel: () =>
          set({ 
            channels: [], 
            currentChannel: null 
          }),

        selectChannel: (channelId) =>
          set((state) => ({
            currentChannel: state.channels.find(c => c.id === channelId) || null
          })),

        // Upload actions
        startUpload: (session) =>
          set((state) => {
            const newUploads = new Map(state.uploads)
            newUploads.set(session.upload_id, session)
            return {
              uploads: newUploads,
              currentUploadId: session.upload_id
            }
          }),

        updateUploadProgress: (uploadId, progress) =>
          set((state) => {
            const upload = state.uploads.get(uploadId)
            if (!upload) return state

            const newUploads = new Map(state.uploads)
            newUploads.set(uploadId, {
              ...upload,
              progress,
              status: 'uploading'
            })
            return { uploads: newUploads }
          }),

        updateUploadStatus: (uploadId, status, error) =>
          set((state) => {
            const upload = state.uploads.get(uploadId)
            if (!upload) return state

            const newUploads = new Map(state.uploads)
            newUploads.set(uploadId, {
              ...upload,
              status,
              error,
              completed_at: status === 'completed' ? new Date() : upload.completed_at
            })
            return { uploads: newUploads }
          }),

        completeUpload: (uploadId, videoId) =>
          set((state) => {
            const upload = state.uploads.get(uploadId)
            if (!upload) return state

            const newUploads = new Map(state.uploads)
            newUploads.set(uploadId, {
              ...upload,
              video_id: videoId,
              status: 'completed',
              completed_at: new Date(),
              progress: {
                ...upload.progress,
                percentage: 100
              }
            })
            return { 
              uploads: newUploads,
              currentUploadId: state.currentUploadId === uploadId ? null : state.currentUploadId
            }
          }),

        cancelUpload: (uploadId) =>
          set((state) => {
            const upload = state.uploads.get(uploadId)
            if (!upload) return state

            const newUploads = new Map(state.uploads)
            newUploads.set(uploadId, {
              ...upload,
              status: 'cancelled'
            })
            return { 
              uploads: newUploads,
              currentUploadId: state.currentUploadId === uploadId ? null : state.currentUploadId
            }
          }),

        clearUpload: (uploadId) =>
          set((state) => {
            const newUploads = new Map(state.uploads)
            newUploads.delete(uploadId)
            return { 
              uploads: newUploads,
              currentUploadId: state.currentUploadId === uploadId ? null : state.currentUploadId
            }
          }),

        // UI State actions
        setAuthenticating: (isAuthenticating) =>
          set({ isAuthenticating }),

        setLoadingChannels: (isLoadingChannels) =>
          set({ isLoadingChannels }),

        setError: (error) =>
          set({ error }),

        // Computed getters
        getCurrentUpload: () => {
          const state = get()
          return state.currentUploadId 
            ? state.uploads.get(state.currentUploadId) 
            : undefined
        },

        getUpload: (uploadId) => {
          return get().uploads.get(uploadId)
        },

        hasChannels: () => {
          return get().channels.length > 0
        },

        getActiveUploads: () => {
          const state = get()
          return Array.from(state.uploads.values()).filter(
            upload => upload.status === 'uploading' || upload.status === 'pending'
          )
        }
      }),
      {
        name: 'youtube-store',
        partialize: (state) => ({
          // Only persist channels and current channel
          channels: state.channels,
          currentChannel: state.currentChannel
        })
      }
    ),
    {
      name: 'YouTubeStore'
    }
  )
)

// Helper hooks
export const useYouTubeChannel = () => {
  return useYouTubeStore((state) => state.currentChannel)
}

export const useYouTubeChannels = () => {
  return useYouTubeStore((state) => state.channels)
}

export const useYouTubeUpload = (uploadId?: string) => {
  const currentUploadId = useYouTubeStore((state) => state.currentUploadId)
  const getUpload = useYouTubeStore((state) => state.getUpload)
  
  const id = uploadId || currentUploadId
  return id ? getUpload(id) : undefined
}

export const useYouTubeActiveUploads = () => {
  return useYouTubeStore((state) => state.getActiveUploads())
}