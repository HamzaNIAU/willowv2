/**
 * YouTube API Client for Frontend
 * Handles all YouTube-related API calls
 */

import { YouTubeChannel, YouTubeUpload, UploadStatus } from './types'

// Base configuration
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// API Error class
export class YouTubeAPIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public code?: string,
    public details?: any
  ) {
    super(message)
    this.name = 'YouTubeAPIError'
  }
}

// Helper function for API calls
async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  
  const defaultHeaders = {
    'Content-Type': 'application/json',
    ...options.headers
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers: defaultHeaders,
      credentials: 'include' // Include cookies for auth
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new YouTubeAPIError(
        error.detail || 'API request failed',
        response.status,
        error.code,
        error
      )
    }

    return await response.json()
  } catch (error) {
    if (error instanceof YouTubeAPIError) {
      throw error
    }
    throw new YouTubeAPIError(
      `Network error: ${error instanceof Error ? error.message : 'Unknown error'}`
    )
  }
}

// YouTube API Client
export const YouTubeAPI = {
  // Authentication
  auth: {
    /**
     * Initiate OAuth flow
     */
    async initiate(redirectUri?: string, state?: string) {
      return apiCall<{ auth_url: string; message: string }>(
        '/api/youtube/auth/initiate',
        {
          method: 'POST',
          body: JSON.stringify({ redirect_uri: redirectUri, state })
        }
      )
    },

    /**
     * Refresh access token
     */
    async refreshToken(refreshToken: string) {
      return apiCall<{ access_token: string; expiry: string }>(
        '/api/youtube/auth/refresh',
        {
          method: 'POST',
          body: JSON.stringify({ refresh_token: refreshToken })
        }
      )
    }
  },

  // Channels
  channels: {
    /**
     * List all connected channels
     */
    async list() {
      return apiCall<{
        channels: YouTubeChannel[]
        count: number
        message?: string
      }>('/api/youtube/channels')
    },

    /**
     * Get specific channel details
     */
    async get(channelId: string) {
      return apiCall<{ channel: YouTubeChannel }>(
        `/api/youtube/channels/${channelId}`
      )
    },

    /**
     * Refresh channel data
     */
    async refresh(channelId: string) {
      return apiCall<{ channel: YouTubeChannel; message: string }>(
        `/api/youtube/channels/${channelId}/refresh`,
        { method: 'POST' }
      )
    },

    /**
     * Disconnect a channel
     */
    async disconnect(channelId: string) {
      return apiCall<{ success: boolean; message: string }>(
        `/api/youtube/channels/${channelId}`,
        { method: 'DELETE' }
      )
    },

    /**
     * Check connection status
     */
    async checkConnection() {
      return apiCall<{
        connected: boolean
        channel_count: number
        channels: Array<{ id: string; name: string }>
      }>('/api/youtube/channels/check-connection', { method: 'POST' })
    }
  },

  // Uploads
  upload: {
    /**
     * Prepare a file for upload
     */
    async prepareFile(file: File, fileType: 'video' | 'thumbnail' = 'video') {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('file_type', fileType)

      const response = await fetch(`${API_BASE}/api/youtube/prepare-upload`, {
        method: 'POST',
        body: formData,
        credentials: 'include'
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }))
        throw new YouTubeAPIError(
          error.detail || 'Failed to prepare upload',
          response.status
        )
      }

      return response.json() as Promise<{
        reference_id: string
        file_name: string
        file_size: string
        mime_type: string
        expires_at: string
        message: string
      }>
    },

    /**
     * List prepared uploads
     */
    async listPrepared() {
      return apiCall<{
        files: Array<{
          reference_id: string
          file_name: string
          file_size: string
          mime_type: string
          uploaded_at: string
          expires_at: string
        }>
      }>('/api/youtube/prepare-upload')
    },

    /**
     * Initiate video upload
     */
    async initiateUpload(
      channelId: string,
      referenceId: string,
      metadata: {
        title: string
        description: string
        tags?: string[]
        category_id?: string
        privacy_status?: 'private' | 'unlisted' | 'public'
        made_for_kids?: boolean
      }
    ) {
      return apiCall<{
        upload_id: string
        status: string
        message: string
        channel_id: string
      }>('/api/youtube/upload', {
        method: 'POST',
        body: JSON.stringify({
          channel_id: channelId,
          reference_id: referenceId,
          metadata
        })
      })
    },

    /**
     * Get upload status
     */
    async getStatus(uploadId: string) {
      return apiCall<{
        upload_id: string
        status: UploadStatus
        progress: number
        video_id?: string
        title: string
        channel_id: string
        created_at: string
        completed_at?: string
        error?: string
      }>(`/api/youtube/upload/status/${uploadId}`)
    },

    /**
     * Upload thumbnail
     */
    async uploadThumbnail(
      videoId: string,
      referenceId: string,
      channelId: string
    ) {
      return apiCall<{ success: boolean; message: string }>(
        '/api/youtube/upload-thumbnail',
        {
          method: 'POST',
          body: JSON.stringify({
            video_id: videoId,
            reference_id: referenceId,
            channel_id: channelId
          })
        }
      )
    },

    /**
     * Get transcription status
     */
    async getTranscriptionStatus(referenceId: string) {
      return apiCall<{
        reference_id: string
        has_transcription: boolean
        has_generated_metadata: boolean
        transcription?: any
        generated_metadata?: any
        status: string
      }>(`/api/youtube/transcription-status/${referenceId}`)
    },

    /**
     * List upload history
     */
    async listHistory(status?: UploadStatus, limit: number = 50) {
      const params = new URLSearchParams()
      if (status) params.append('status', status)
      params.append('limit', limit.toString())

      return apiCall<{
        uploads: YouTubeUpload[]
        count: number
      }>(`/api/youtube/uploads?${params}`)
    },

    /**
     * Cancel an upload
     */
    async cancel(uploadId: string) {
      return apiCall<{ success: boolean; message: string }>(
        `/api/youtube/upload/${uploadId}`,
        { method: 'DELETE' }
      )
    }
  },

  // Analytics (placeholder for future implementation)
  analytics: {
    /**
     * Get video analytics
     */
    async getVideoAnalytics(
      channelId: string,
      videoId: string,
      startDate: string,
      endDate: string
    ) {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate
      })

      return apiCall<any>(
        `/api/youtube/analytics/video/${videoId}?${params}`
      )
    },

    /**
     * Get channel analytics
     */
    async getChannelAnalytics(
      channelId: string,
      startDate: string,
      endDate: string
    ) {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate
      })

      return apiCall<any>(
        `/api/youtube/analytics/channel/${channelId}?${params}`
      )
    }
  }
}

// Helper functions
export const YouTubeHelpers = {
  /**
   * Format file size
   */
  formatFileSize(bytes: number): string {
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let size = bytes
    let unitIndex = 0

    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024
      unitIndex++
    }

    return `${size.toFixed(2)} ${units[unitIndex]}`
  },

  /**
   * Format duration
   */
  formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`
  },

  /**
   * Format view count
   */
  formatCount(count: number): string {
    if (count >= 1_000_000_000) {
      return `${(count / 1_000_000_000).toFixed(1)}B`
    } else if (count >= 1_000_000) {
      return `${(count / 1_000_000).toFixed(1)}M`
    } else if (count >= 1_000) {
      return `${(count / 1_000).toFixed(1)}K`
    }
    return count.toString()
  },

  /**
   * Validate video metadata
   */
  validateMetadata(metadata: any): { valid: boolean; errors: string[] } {
    const errors: string[] = []

    if (!metadata.title || metadata.title.length === 0) {
      errors.push('Title is required')
    } else if (metadata.title.length > 100) {
      errors.push('Title must be 100 characters or less')
    }

    if (metadata.description && metadata.description.length > 5000) {
      errors.push('Description must be 5000 characters or less')
    }

    if (metadata.tags) {
      const totalChars = metadata.tags.join('').length
      if (totalChars > 500) {
        errors.push('Total tag characters must be 500 or less')
      }
      if (metadata.tags.length > 500) {
        errors.push('Maximum 500 tags allowed')
      }
    }

    return {
      valid: errors.length === 0,
      errors
    }
  },

  /**
   * Get video URL
   */
  getVideoUrl(videoId: string): string {
    return `https://youtube.com/watch?v=${videoId}`
  },

  /**
   * Get channel URL
   */
  getChannelUrl(channelId: string): string {
    return `https://youtube.com/channel/${channelId}`
  }
}

// Export default client
export default YouTubeAPI