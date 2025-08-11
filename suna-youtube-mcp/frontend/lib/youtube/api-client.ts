/**
 * YouTube API Client for Frontend
 * Uses axios for HTTP requests following Suna's patterns
 */

import axios, { AxiosInstance, AxiosError } from 'axios'
import { 
  YouTubeChannel,
  YouTubeUpload,
  UploadReference,
  UploadRequest,
  UploadResponse,
  ChannelListResponse,
  UploadProgressResponse,
  VideoAnalytics,
  ChannelAnalytics,
  UploadStatus
} from './types'

// Create axios instance with default config
const createAPIClient = (): AxiosInstance => {
  const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  
  const client = axios.create({
    baseURL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  // Add auth interceptor
  client.interceptors.request.use(
    (config) => {
      // Get token from Supabase or your auth provider
      const token = typeof window !== 'undefined' 
        ? localStorage.getItem('supabase.auth.token')
        : null
      
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      
      return config
    },
    (error) => {
      return Promise.reject(error)
    }
  )

  // Add response interceptor for error handling
  client.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      if (error.response?.status === 401) {
        // Handle unauthorized - redirect to login or refresh token
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
      }
      
      // Extract error message
      const message = (error.response?.data as any)?.detail || 
                     (error.response?.data as any)?.message ||
                     error.message ||
                     'An unexpected error occurred'
      
      return Promise.reject(new Error(message))
    }
  )

  return client
}

const api = createAPIClient()

/**
 * YouTube API methods organized by resource
 */
export const YouTubeAPI = {
  /**
   * Authentication endpoints
   */
  auth: {
    initiate: async (redirectUri?: string, state?: string) => {
      const response = await api.post('/api/youtube/auth/initiate', {
        redirect_uri: redirectUri,
        state
      })
      return response.data
    },
    
    refresh: async (refreshToken: string) => {
      const response = await api.post('/api/youtube/auth/refresh', {
        refresh_token: refreshToken
      })
      return response.data
    }
  },

  /**
   * Channel management endpoints
   */
  channels: {
    list: async (): Promise<ChannelListResponse> => {
      const response = await api.get('/api/youtube/channels')
      return response.data
    },
    
    get: async (channelId: string): Promise<YouTubeChannel> => {
      const response = await api.get(`/api/youtube/channels/${channelId}`)
      return response.data
    },
    
    refresh: async (channelId: string): Promise<YouTubeChannel> => {
      const response = await api.post(`/api/youtube/channels/${channelId}/refresh`)
      return response.data
    },
    
    disconnect: async (channelId: string): Promise<void> => {
      await api.delete(`/api/youtube/channels/${channelId}`)
    },
    
    checkConnection: async (): Promise<{ connected: boolean; channel_count: number }> => {
      const response = await api.get('/api/youtube/channels/status')
      return response.data
    }
  },

  /**
   * Upload management endpoints
   */
  upload: {
    prepareFile: async (file: File, fileType?: 'video' | 'thumbnail'): Promise<UploadReference> => {
      const formData = new FormData()
      formData.append('file', file)
      if (fileType) {
        formData.append('file_type', fileType)
      }
      
      const response = await api.post('/api/youtube/upload/prepare-upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      
      return response.data
    },
    
    initiateUpload: async (
      channelId: string,
      referenceId: string,
      metadata: any
    ): Promise<UploadResponse> => {
      const request: UploadRequest = {
        channel_id: channelId,
        reference_id: referenceId,
        metadata
      }
      
      const response = await api.post('/api/youtube/upload', request)
      return response.data
    },
    
    getStatus: async (uploadId: string): Promise<UploadProgressResponse> => {
      const response = await api.get(`/api/youtube/upload/status/${uploadId}`)
      return response.data
    },
    
    cancel: async (uploadId: string): Promise<void> => {
      await api.post(`/api/youtube/upload/cancel/${uploadId}`)
    },
    
    uploadThumbnail: async (
      videoId: string,
      referenceId: string,
      channelId: string
    ): Promise<void> => {
      await api.post('/api/youtube/upload/thumbnail', {
        video_id: videoId,
        reference_id: referenceId,
        channel_id: channelId
      })
    },
    
    getTranscriptionStatus: async (referenceId: string): Promise<{
      status: 'pending' | 'completed' | 'failed'
      transcription?: any
      error?: string
    }> => {
      const response = await api.get(`/api/youtube/upload/transcription/${referenceId}`)
      return response.data
    },
    
    listHistory: async (
      status?: UploadStatus,
      limit: number = 50
    ): Promise<{ uploads: YouTubeUpload[]; total: number }> => {
      const params = new URLSearchParams()
      if (status) params.append('status', status)
      params.append('limit', limit.toString())
      
      const response = await api.get(`/api/youtube/upload/history?${params}`)
      return response.data
    },
    
    listPrepared: async (): Promise<UploadReference[]> => {
      const response = await api.get('/api/youtube/upload/prepared')
      return response.data
    }
  },

  /**
   * Analytics endpoints
   */
  analytics: {
    getVideoAnalytics: async (
      videoId: string,
      startDate?: string,
      endDate?: string
    ): Promise<VideoAnalytics> => {
      const params = new URLSearchParams()
      if (startDate) params.append('start_date', startDate)
      if (endDate) params.append('end_date', endDate)
      
      const response = await api.get(`/api/youtube/analytics/video/${videoId}?${params}`)
      return response.data
    },
    
    getChannelAnalytics: async (
      channelId: string,
      startDate?: string,
      endDate?: string
    ): Promise<ChannelAnalytics> => {
      const params = new URLSearchParams()
      if (startDate) params.append('start_date', startDate)
      if (endDate) params.append('end_date', endDate)
      
      const response = await api.get(`/api/youtube/analytics/channel/${channelId}?${params}`)
      return response.data
    },
    
    getTopVideos: async (
      channelId: string,
      limit: number = 10
    ): Promise<Array<{ video_id: string; title: string; views: number }>> => {
      const response = await api.get(`/api/youtube/analytics/channel/${channelId}/top-videos?limit=${limit}`)
      return response.data
    }
  },

  /**
   * Utility endpoints
   */
  utils: {
    getCategories: async (): Promise<Array<{ id: string; title: string }>> => {
      const response = await api.get('/api/youtube/utils/categories')
      return response.data
    },
    
    validateMetadata: async (metadata: any): Promise<{
      valid: boolean
      errors?: string[]
    }> => {
      const response = await api.post('/api/youtube/utils/validate-metadata', metadata)
      return response.data
    },
    
    generateMetadata: async (
      transcription: string,
      context?: string
    ): Promise<{
      title: string
      description: string
      tags: string[]
      category_id: string
    }> => {
      const response = await api.post('/api/youtube/utils/generate-metadata', {
        transcription,
        context
      })
      return response.data
    }
  }
}

/**
 * Helper function to handle file uploads with progress
 */
export async function uploadFileWithProgress(
  file: File,
  onProgress?: (progress: number) => void
): Promise<UploadReference> {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/api/youtube/upload/prepare-upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total) {
        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress?.(progress)
      }
    }
  })
  
  return response.data
}

/**
 * Helper to format file size
 */
export function formatFileSize(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0
  
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  
  return `${size.toFixed(2)} ${units[unitIndex]}`
}

/**
 * Helper to format duration
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`
  } else {
    return `${secs}s`
  }
}

export default YouTubeAPI