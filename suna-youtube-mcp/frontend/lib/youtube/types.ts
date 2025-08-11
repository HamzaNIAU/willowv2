/**
 * TypeScript Type Definitions for YouTube MCP Frontend
 */

// Enums
export enum PrivacyStatus {
  PRIVATE = 'private',
  UNLISTED = 'unlisted',
  PUBLIC = 'public'
}

export enum UploadStatus {
  PENDING = 'pending',
  UPLOADING = 'uploading',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
  SCHEDULED = 'scheduled'
}

export enum FileType {
  VIDEO = 'video',
  THUMBNAIL = 'thumbnail'
}

// YouTube Models
export interface YouTubeChannel {
  id: string
  name: string
  custom_url?: string
  thumbnail_url?: string
  subscriber_count: number
  view_count: number
  video_count: number
  description?: string
  statistics?: {
    subscribers: number | string
    views: number | string
    videos: number | string
    formatted?: {
      subscribers: string
      views: string
      videos: string
    }
  }
  capabilities?: {
    upload: boolean
    analytics: boolean
    management: boolean
    streaming: boolean
    monetization: boolean
  }
  has_token?: boolean
}

export interface YouTubeVideo {
  id: string
  channel_id: string
  title: string
  description: string
  thumbnail_url?: string
  published_at: string
  view_count: number
  like_count: number
  comment_count: number
  duration?: string
  privacy_status: PrivacyStatus
  tags: string[]
}

export interface YouTubeVideoMetadata {
  title: string
  description: string
  tags?: string[]
  category_id?: string
  privacy_status?: PrivacyStatus
  made_for_kids?: boolean
  notify_subscribers?: boolean
  publish_at?: Date | string
}

// Upload Models
export interface VideoFileReference {
  id: string
  user_id: string
  file_name: string
  file_path?: string
  file_size: number
  mime_type: string
  checksum?: string
  uploaded_at: string
  expires_at: string
  transcription?: VideoTranscription
  generated_metadata?: GeneratedMetadata[]
  is_temporary: boolean
}

export interface UploadReference {
  id: string
  user_id: string
  reference_id: string
  file_name: string
  file_size: string
  file_type: FileType
  mime_type: string
  status: 'pending' | 'used' | 'expired'
  created_at: string
  used_at?: string
}

export interface YouTubeUpload {
  id: string
  upload_id?: string  // Alias for id
  user_id: string
  channel_id: string
  video_id?: string
  title: string
  description: string
  tags: string[]
  category_id: string
  privacy_status: PrivacyStatus
  made_for_kids: boolean
  file_name: string
  file_size: number | string
  mime_type: string
  upload_status: UploadStatus
  upload_progress: number
  status_message?: string
  error_message?: string
  scheduled_for?: string
  video_reference_id?: string
  thumbnail_reference_id?: string
  created_at: string
  updated_at?: string
  completed_at?: string
}

export interface UploadSession {
  upload_id: string
  channel_id: string
  video_id?: string
  title: string
  status: UploadStatus
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
  created_at: Date | string
  completed_at?: Date | string
}

// Analytics Models
export interface VideoAnalytics {
  video_id: string
  channel_id: string
  period_start: string
  period_end: string
  views: number
  watch_time_minutes: number
  average_view_duration_seconds: number
  likes: number
  dislikes: number
  comments: number
  shares: number
  subscribers_gained: number
  subscribers_lost: number
  estimated_revenue?: number
  impressions: number
  click_through_rate: number
}

export interface ChannelAnalytics {
  channel_id: string
  period_start: string
  period_end: string
  total_views: number
  total_watch_time_minutes: number
  total_subscribers: number
  subscribers_gained: number
  subscribers_lost: number
  estimated_revenue?: number
  videos_published: number
  average_view_duration_seconds: number
  top_videos: Array<{
    video_id: string
    title: string
    views: number
  }>
  demographics?: {
    age_groups: Record<string, number>
    genders: Record<string, number>
    countries: Record<string, number>
  }
}

// Transcription Models
export interface TranscriptionSegment {
  text: string
  start: number
  end: number
  confidence?: number
}

export interface VideoTranscription {
  text: string
  language: string
  duration: number
  segments: TranscriptionSegment[]
  processed_at: string
}

export interface GeneratedMetadata {
  title: string
  description: string
  tags: string[]
  category?: string
  thumbnail_suggestions?: string[]
  confidence: number
}

// Request/Response Models
export interface UploadRequest {
  channel_id: string
  reference_id: string
  metadata: YouTubeVideoMetadata
  thumbnail_reference_id?: string
  scheduled_for?: string
}

export interface UploadResponse {
  upload_id: string
  video_id?: string
  status: UploadStatus
  message: string
  channel_id: string
  channel_name?: string
  scheduled_for?: string
}

export interface ChannelListResponse {
  channels: YouTubeChannel[]
  count: number
  message?: string
}

export interface UploadProgressResponse {
  upload_id: string
  status: UploadStatus
  progress: number
  bytes_uploaded?: number
  total_bytes?: number
  formatted_uploaded?: string
  formatted_total?: string
  elapsed_seconds?: number
  upload_speed_bps?: number
  estimated_time_remaining?: number
  video_id?: string
  error?: string
}

// OAuth Models
export interface OAuthToken {
  access_token: string
  refresh_token: string
  token_type: string
  expiry: string
  scopes: string[]
}

export interface OAuthConfig {
  client_id: string
  client_secret: string
  redirect_uri: string
  scopes: string[]
  auth_url: string
  token_url: string
}

// Error Models
export interface YouTubeError {
  code: number
  message: string
  status: string
  details?: any[]
}

export interface UploadError {
  upload_id: string
  error_type: string
  error_message: string
  timestamp: string
  retry_count: number
  can_retry: boolean
}

// Tool Response Types (for AI integration)
export interface YouTubeAuthToolResponse {
  type: 'youtube-auth'
  auth_url: string
  message: string
  instructions: string[]
}

export interface YouTubeUploadToolResponse {
  type: 'youtube-upload' | 'youtube-upload-scheduled'
  upload_id: string
  video_id?: string
  title: string
  channel_name: string
  channel_id: string
  file_name?: string
  file_size?: string
  message: string
  has_thumbnail?: boolean
  scheduled_for?: string
  interpretation?: string
}

export interface YouTubeChannelsToolResponse {
  type: 'youtube-channels' | 'youtube-channels-status'
  channels?: YouTubeChannel[]
  count?: number
  enabled?: boolean
  channel_count?: number
  message: string
}

// UI Component Props
export interface YouTubeAuthButtonProps {
  authUrl?: string
  onSuccess?: (channel: any) => void
  onError?: (error: string) => void
  className?: string
}

export interface YouTubeUploadProgressProps {
  uploadId: string
  onComplete?: (videoId: string) => void
  onError?: (error: string) => void
  onCancel?: () => void
  className?: string
}

export interface YouTubeChannelSelectorProps {
  channels: YouTubeChannel[]
  selectedChannelId?: string
  onSelect: (channelId: string) => void
  className?: string
}

export interface YouTubeVideoCardProps {
  video: YouTubeVideo
  showChannel?: boolean
  showStats?: boolean
  onPlay?: () => void
  onEdit?: () => void
  onDelete?: () => void
  className?: string
}

// Utility Types
export type YouTubeCategory = {
  id: string
  title: string
  assignable: boolean
}

export const YOUTUBE_CATEGORIES: YouTubeCategory[] = [
  { id: '1', title: 'Film & Animation', assignable: true },
  { id: '2', title: 'Cars & Vehicles', assignable: true },
  { id: '10', title: 'Music', assignable: true },
  { id: '15', title: 'Pets & Animals', assignable: true },
  { id: '17', title: 'Sports', assignable: true },
  { id: '19', title: 'Travel & Events', assignable: true },
  { id: '20', title: 'Gaming', assignable: true },
  { id: '22', title: 'People & Blogs', assignable: true },
  { id: '23', title: 'Comedy', assignable: true },
  { id: '24', title: 'Entertainment', assignable: true },
  { id: '25', title: 'News & Politics', assignable: true },
  { id: '26', title: 'How-to & Style', assignable: true },
  { id: '27', title: 'Education', assignable: true },
  { id: '28', title: 'Science & Technology', assignable: true }
]

// Export type guards
export const isYouTubeChannel = (obj: any): obj is YouTubeChannel => {
  return obj && typeof obj.id === 'string' && typeof obj.name === 'string'
}

export const isYouTubeVideo = (obj: any): obj is YouTubeVideo => {
  return obj && typeof obj.id === 'string' && typeof obj.title === 'string'
}

export const isUploadSession = (obj: any): obj is UploadSession => {
  return obj && typeof obj.upload_id === 'string' && obj.progress !== undefined
}