/**
 * YouTube Upload Progress Component
 * Displays real-time upload progress with status updates
 */

import React, { useEffect, useState } from 'react'
import { Progress, Card, Text, Badge, Button, Flex } from '@radix-ui/themes'
import { 
  Upload, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Clock,
  Pause,
  Play,
  X
} from 'lucide-react'
import { useYouTubeStore, useYouTubeUpload } from '@/stores/youtube-store'

interface YouTubeUploadProgressProps {
  uploadId: string
  onComplete?: (videoId: string) => void
  onError?: (error: string) => void
  onCancel?: () => void
  className?: string
}

export function YouTubeUploadProgress({
  uploadId,
  onComplete,
  onError,
  onCancel,
  className
}: YouTubeUploadProgressProps) {
  const upload = useYouTubeUpload(uploadId)
  const { updateUploadProgress, updateUploadStatus, cancelUpload } = useYouTubeStore()
  const [isPolling, setIsPolling] = useState(true)

  // Poll for upload status
  useEffect(() => {
    if (!isPolling || !uploadId) return
    if (upload?.status === 'completed' || upload?.status === 'failed' || upload?.status === 'cancelled') {
      setIsPolling(false)
      return
    }

    const pollStatus = async () => {
      try {
        const response = await fetch(`/api/youtube/upload/status/${uploadId}`)
        const data = await response.json()

        if (data.progress !== undefined) {
          updateUploadProgress(uploadId, {
            percentage: data.progress,
            bytes_uploaded: data.bytes_uploaded || 0,
            total_bytes: data.total_bytes || 0,
            formatted_uploaded: data.formatted_uploaded || '0 B',
            formatted_total: data.formatted_total || '0 B'
          })
        }

        if (data.status) {
          updateUploadStatus(uploadId, data.status, data.error)

          if (data.status === 'completed' && data.video_id) {
            onComplete?.(data.video_id)
            setIsPolling(false)
          } else if (data.status === 'failed') {
            onError?.(data.error || 'Upload failed')
            setIsPolling(false)
          }
        }
      } catch (error) {
        console.error('[UploadProgress] Failed to poll status:', error)
      }
    }

    const interval = setInterval(pollStatus, 2000) // Poll every 2 seconds
    pollStatus() // Initial poll

    return () => clearInterval(interval)
  }, [uploadId, isPolling, upload?.status, updateUploadProgress, updateUploadStatus, onComplete, onError])

  const handleCancel = async () => {
    try {
      setIsPolling(false)
      cancelUpload(uploadId)
      
      // Call API to cancel on backend
      await fetch(`/api/youtube/upload/${uploadId}`, {
        method: 'DELETE'
      })

      onCancel?.()
    } catch (error) {
      console.error('[UploadProgress] Failed to cancel upload:', error)
    }
  }

  if (!upload) {
    return null
  }

  const getStatusIcon = () => {
    switch (upload.status) {
      case 'completed':
        return <CheckCircle2 className="h-5 w-5 text-green-500" />
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />
      case 'cancelled':
        return <XCircle className="h-5 w-5 text-gray-500" />
      case 'uploading':
        return <Upload className="h-5 w-5 text-blue-500 animate-pulse" />
      case 'scheduled':
        return <Clock className="h-5 w-5 text-yellow-500" />
      default:
        return <AlertCircle className="h-5 w-5 text-gray-500" />
    }
  }

  const getStatusColor = () => {
    switch (upload.status) {
      case 'completed':
        return 'green'
      case 'failed':
        return 'red'
      case 'cancelled':
        return 'gray'
      case 'uploading':
        return 'blue'
      case 'scheduled':
        return 'yellow'
      default:
        return 'gray'
    }
  }

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)

    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`
    }
    return `${secs}s`
  }

  return (
    <Card className={className}>
      <Flex direction="column" gap="3">
        {/* Header */}
        <Flex justify="between" align="center">
          <Flex align="center" gap="2">
            {getStatusIcon()}
            <Text size="2" weight="bold" className="line-clamp-1">
              {upload.title}
            </Text>
          </Flex>
          <Badge color={getStatusColor()} variant="soft">
            {upload.status}
          </Badge>
        </Flex>

        {/* Progress Bar */}
        {upload.status === 'uploading' && (
          <>
            <Progress 
              value={upload.progress.percentage} 
              size="2"
              color="blue"
            />
            
            {/* Progress Details */}
            <Flex justify="between" align="center">
              <Text size="1" color="gray">
                {upload.progress.formatted_uploaded} / {upload.progress.formatted_total}
              </Text>
              <Text size="1" color="gray">
                {upload.progress.percentage.toFixed(1)}%
              </Text>
            </Flex>

            {/* Speed and Time */}
            {upload.timing && (
              <Flex justify="between" align="center">
                <Text size="1" color="gray">
                  Speed: {upload.timing.upload_speed_formatted}
                </Text>
                <Text size="1" color="gray">
                  ETA: {formatTime(upload.timing.estimated_time_remaining)}
                </Text>
              </Flex>
            )}
          </>
        )}

        {/* Error Message */}
        {upload.status === 'failed' && upload.error && (
          <Card variant="surface" style={{ backgroundColor: 'var(--red-2)' }}>
            <Text size="1" color="red">
              {upload.error}
            </Text>
          </Card>
        )}

        {/* Success Message */}
        {upload.status === 'completed' && upload.video_id && (
          <Card variant="surface" style={{ backgroundColor: 'var(--green-2)' }}>
            <Flex align="center" gap="2">
              <Text size="1" color="green">
                Video uploaded successfully!
              </Text>
              <Button
                size="1"
                variant="ghost"
                onClick={() => window.open(`https://youtube.com/watch?v=${upload.video_id}`, '_blank')}
              >
                View on YouTube
              </Button>
            </Flex>
          </Card>
        )}

        {/* Actions */}
        {upload.status === 'uploading' && (
          <Flex gap="2">
            <Button
              size="2"
              variant="soft"
              color="red"
              onClick={handleCancel}
            >
              <X className="h-4 w-4 mr-1" />
              Cancel Upload
            </Button>
          </Flex>
        )}
      </Flex>
    </Card>
  )
}

/**
 * Multiple Upload Progress Component
 * Shows all active uploads
 */
export function YouTubeActiveUploads() {
  const activeUploads = useYouTubeStore(state => state.getActiveUploads())

  if (activeUploads.length === 0) {
    return null
  }

  return (
    <div className="space-y-3">
      <Text size="3" weight="bold">Active Uploads</Text>
      {activeUploads.map(upload => (
        <YouTubeUploadProgress
          key={upload.upload_id}
          uploadId={upload.upload_id}
        />
      ))}
    </div>
  )
}