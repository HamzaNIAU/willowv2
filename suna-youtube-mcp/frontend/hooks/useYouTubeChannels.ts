/**
 * React Query hooks for YouTube data fetching
 * Following Suna's tech stack with TanStack Query v5
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { YouTubeAPI } from '@/lib/youtube/api-client'
import { YouTubeChannel, YouTubeUpload } from '@/lib/youtube/types'
import { useYouTubeStore } from '@/stores/youtube-store'

// Query keys
export const youtubeKeys = {
  all: ['youtube'] as const,
  channels: () => [...youtubeKeys.all, 'channels'] as const,
  channel: (id: string) => [...youtubeKeys.channels(), id] as const,
  uploads: () => [...youtubeKeys.all, 'uploads'] as const,
  upload: (id: string) => [...youtubeKeys.uploads(), id] as const,
  preparedFiles: () => [...youtubeKeys.all, 'prepared-files'] as const,
}

/**
 * Fetch YouTube channels
 */
export function useYouTubeChannels() {
  const { setChannels, setLoadingChannels, setError } = useYouTubeStore()

  return useQuery({
    queryKey: youtubeKeys.channels(),
    queryFn: async () => {
      setLoadingChannels(true)
      try {
        const response = await YouTubeAPI.channels.list()
        setChannels(response.channels)
        setError(null)
        return response
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to fetch channels'
        setError(message)
        throw error
      } finally {
        setLoadingChannels(false)
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime in v4)
  })
}

/**
 * Fetch single channel details
 */
export function useYouTubeChannel(channelId: string) {
  return useQuery({
    queryKey: youtubeKeys.channel(channelId),
    queryFn: () => YouTubeAPI.channels.get(channelId),
    enabled: !!channelId,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Refresh channel data mutation
 */
export function useRefreshChannel() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (channelId: string) => YouTubeAPI.channels.refresh(channelId),
    onSuccess: (data, channelId) => {
      // Invalidate channel queries
      queryClient.invalidateQueries({ queryKey: youtubeKeys.channel(channelId) })
      queryClient.invalidateQueries({ queryKey: youtubeKeys.channels() })
    },
  })
}

/**
 * Disconnect channel mutation
 */
export function useDisconnectChannel() {
  const queryClient = useQueryClient()
  const { removeChannel } = useYouTubeStore()

  return useMutation({
    mutationFn: (channelId: string) => YouTubeAPI.channels.disconnect(channelId),
    onSuccess: (_, channelId) => {
      removeChannel(channelId)
      queryClient.invalidateQueries({ queryKey: youtubeKeys.channels() })
    },
  })
}

/**
 * Check connection status
 */
export function useYouTubeConnectionStatus() {
  return useQuery({
    queryKey: [...youtubeKeys.all, 'connection-status'],
    queryFn: () => YouTubeAPI.channels.checkConnection(),
    staleTime: 30 * 1000, // 30 seconds
  })
}

/**
 * Fetch upload history
 */
export function useYouTubeUploads(status?: string, limit: number = 50) {
  return useQuery({
    queryKey: [...youtubeKeys.uploads(), { status, limit }],
    queryFn: () => YouTubeAPI.upload.listHistory(status as any, limit),
    staleTime: 1 * 60 * 1000, // 1 minute
  })
}

/**
 * Fetch single upload status
 */
export function useYouTubeUploadStatus(uploadId: string, enabled = true) {
  return useQuery({
    queryKey: youtubeKeys.upload(uploadId),
    queryFn: () => YouTubeAPI.upload.getStatus(uploadId),
    enabled: enabled && !!uploadId,
    refetchInterval: (data) => {
      // Poll while uploading
      if (data?.status === 'uploading' || data?.status === 'processing') {
        return 2000 // 2 seconds
      }
      return false
    },
  })
}

/**
 * Prepare file for upload mutation
 */
export function usePrepareUpload() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ file, fileType }: { file: File; fileType?: 'video' | 'thumbnail' }) =>
      YouTubeAPI.upload.prepareFile(file, fileType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: youtubeKeys.preparedFiles() })
    },
  })
}

/**
 * Initiate upload mutation
 */
export function useInitiateUpload() {
  const { startUpload } = useYouTubeStore()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: {
      channelId: string
      referenceId: string
      metadata: any
    }) => YouTubeAPI.upload.initiateUpload(
      params.channelId,
      params.referenceId,
      params.metadata
    ),
    onSuccess: (data) => {
      // Create upload session in store
      startUpload({
        upload_id: data.upload_id,
        channel_id: data.channel_id,
        title: data.message,
        status: 'uploading',
        progress: {
          percentage: 0,
          bytes_uploaded: 0,
          total_bytes: 0,
          formatted_uploaded: '0 B',
          formatted_total: '0 B',
        },
        created_at: new Date(),
      })
      
      // Invalidate uploads list
      queryClient.invalidateQueries({ queryKey: youtubeKeys.uploads() })
    },
  })
}

/**
 * Cancel upload mutation
 */
export function useCancelUpload() {
  const { cancelUpload } = useYouTubeStore()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (uploadId: string) => YouTubeAPI.upload.cancel(uploadId),
    onSuccess: (_, uploadId) => {
      cancelUpload(uploadId)
      queryClient.invalidateQueries({ queryKey: youtubeKeys.upload(uploadId) })
      queryClient.invalidateQueries({ queryKey: youtubeKeys.uploads() })
    },
  })
}

/**
 * Upload thumbnail mutation
 */
export function useUploadThumbnail() {
  return useMutation({
    mutationFn: (params: {
      videoId: string
      referenceId: string
      channelId: string
    }) => YouTubeAPI.upload.uploadThumbnail(
      params.videoId,
      params.referenceId,
      params.channelId
    ),
  })
}

/**
 * Get transcription status
 */
export function useTranscriptionStatus(referenceId: string, enabled = true) {
  return useQuery({
    queryKey: [...youtubeKeys.all, 'transcription', referenceId],
    queryFn: () => YouTubeAPI.upload.getTranscriptionStatus(referenceId),
    enabled: enabled && !!referenceId,
    refetchInterval: (data) => {
      // Poll while pending
      if (data?.status === 'pending') {
        return 5000 // 5 seconds
      }
      return false
    },
  })
}

/**
 * List prepared files
 */
export function usePreparedFiles() {
  return useQuery({
    queryKey: youtubeKeys.preparedFiles(),
    queryFn: () => YouTubeAPI.upload.listPrepared(),
    staleTime: 30 * 1000, // 30 seconds
  })
}