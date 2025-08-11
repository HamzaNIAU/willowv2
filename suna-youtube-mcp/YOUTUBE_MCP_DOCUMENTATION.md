# YouTube MCP Documentation for Suna

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [OAuth Flow](#oauth-flow)
4. [File Upload System](#file-upload-system)
5. [Tools and Capabilities](#tools-and-capabilities)
6. [API Endpoints](#api-endpoints)
7. [Frontend Integration](#frontend-integration)
8. [Database Schema](#database-schema)
9. [Configuration](#configuration)
10. [Usage Examples](#usage-examples)
11. [Troubleshooting](#troubleshooting)

## Overview

The YouTube MCP (Model Context Protocol) for Suna provides comprehensive YouTube integration capabilities, allowing AI agents to authenticate with YouTube, upload videos, manage channels, and retrieve analytics. This implementation is adapted from Morphic's YouTube MCP to work with Suna's FastAPI/Python backend and Next.js frontend.

### Key Features
- 🔐 **OAuth 2.0 Authentication** - Secure Google OAuth flow with token refresh
- 📹 **Video Upload** - Resumable uploads for large files with progress tracking
- 📊 **Analytics** - Video and channel analytics retrieval
- 🗓️ **Scheduling** - Natural language scheduling for future uploads
- 🎨 **Thumbnail Support** - Automatic thumbnail upload
- 🤖 **AI Integration** - Seamless integration with LiteLLM agents
- 💾 **File Management** - Temporary file storage with automatic cleanup
- 🔄 **Multi-Channel Support** - Manage multiple YouTube channels

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                    │
├─────────────────────────────────────────────────────────────┤
│  Components:                                                 │
│  - YouTubeAuthButton    - Authentication UI                 │
│  - YouTubeUploadProgress - Upload status display            │
│  - YouTubeChannelSelector - Channel selection               │
│  └─ Zustand Store (youtube-store.ts)                       │
├─────────────────────────────────────────────────────────────┤
│                     Backend (FastAPI)                        │
├─────────────────────────────────────────────────────────────┤
│  OAuth System:                                              │
│  - oauth.py         - OAuth flow handler                    │
│  - client.py        - YouTube API client                    │
│  - channels.py      - Channel management                    │
│                                                              │
│  File System:                                               │
│  - file_manager.py  - File reference management             │
│  - upload_stream.py - Chunked upload handler                │
│                                                              │
│  LiteLLM Tools:                                             │
│  - authenticate.py  - OAuth authentication tool             │
│  - upload_video.py - Video upload tool                      │
│  - channels.py     - Channel listing tool                   │
│  - loader.py       - Dynamic tool loader                    │
├─────────────────────────────────────────────────────────────┤
│                    Database (Supabase)                       │
├─────────────────────────────────────────────────────────────┤
│  Tables:                                                     │
│  - youtube_channels       - Channel data & tokens           │
│  - youtube_uploads        - Upload tracking                 │
│  - video_file_references  - Temporary file storage          │
│  - upload_references      - Pending upload queue            │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Authentication Flow**
   ```
   User → Frontend → Backend OAuth → Google OAuth → Callback → Store Token → Channel Saved
   ```

2. **Upload Flow**
   ```
   File Upload → Create Reference → AI Tools → Upload Video → Streaming Upload → YouTube
   ```

3. **Tool Execution Flow**
   ```
   AI Agent → LiteLLM → Tool Loader → Tool Execution → Response → UI Update
   ```

## OAuth Flow

### 1. Initiation
The OAuth flow begins when the AI agent uses the `youtube_authenticate` tool:

```python
# Tool returns authentication URL
{
    "type": "youtube-auth",
    "auth_url": "https://accounts.google.com/o/oauth2/auth?...",
    "message": "Click the button below to connect your YouTube account"
}
```

### 2. User Authorization
- Frontend displays authentication button
- User clicks button → Opens popup window
- User authorizes application on Google
- Google redirects to callback URL with authorization code

### 3. Token Exchange
Backend callback endpoint (`/api/youtube/auth/callback`):
1. Receives authorization code
2. Exchanges code for access/refresh tokens
3. Fetches user's YouTube channel information
4. Stores channel data with encrypted tokens
5. Returns success HTML that closes popup

### 4. Token Management
- Tokens stored encrypted in Supabase
- Automatic refresh when token expires (5-minute buffer)
- Refresh token used to obtain new access tokens
- Token scopes determine available capabilities

### OAuth Scopes
```python
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",        # Upload videos
    "https://www.googleapis.com/auth/youtube.readonly",      # Read channel data
    "https://www.googleapis.com/auth/yt-analytics.readonly", # Analytics
    "https://www.googleapis.com/auth/youtube.force-ssl",     # Management
]
```

## File Upload System

### File Reference System
The file manager creates temporary references for uploaded files:

```python
# File reference structure
VideoFileReference:
    id: str              # 32-character hex reference ID
    user_id: str         # User who uploaded
    file_name: str       # Original filename
    file_path: str       # Temporary storage path
    file_size: int       # Size in bytes
    mime_type: str       # MIME type
    checksum: str        # SHA256 hash
    expires_at: datetime # Auto-cleanup time (24 hours)
    transcription: dict  # Optional AI transcription
    generated_metadata: list # AI-generated titles/descriptions
```

### Upload Process

1. **File Preparation**
   ```python
   # Frontend uploads file to /api/youtube/prepare-upload
   POST /api/youtube/prepare-upload
   Content-Type: multipart/form-data
   
   # Returns reference ID
   {
       "referenceId": "a1b2c3d4e5f6...",
       "fileName": "video.mp4",
       "fileSize": "1.5 GB",
       "expiresAt": "2024-01-02T00:00:00Z"
   }
   ```

2. **Resumable Upload**
   - Files uploaded in 256MB chunks
   - Automatic retry on failure (3 attempts)
   - Progress tracking with callbacks
   - Resume capability for interrupted uploads

3. **Upload Session**
   ```python
   UploadSession:
       upload_url: str          # YouTube resumable upload URL
       total_bytes: int         # Total file size
       bytes_uploaded: int      # Current progress
       video_id: str           # YouTube video ID when complete
       progress_percentage: float
       upload_speed: float     # Bytes per second
       estimated_time_remaining: float
   ```

## Tools and Capabilities

### 1. youtube_authenticate
**Purpose**: Start OAuth authentication flow  
**Parameters**: 
- `redirect_uri` (optional): OAuth callback URL
- `state` (optional): CSRF protection token

**Returns**:
```json
{
    "type": "youtube-auth",
    "auth_url": "https://accounts.google.com/...",
    "message": "Click to authenticate",
    "instructions": ["Step 1", "Step 2", ...]
}
```

### 2. youtube_upload_video
**Purpose**: Upload video to YouTube channel  
**Parameters**:
- `channel_id`: Target channel ID
- `title`: Video title
- `description`: Video description
- `tags`: List of tags
- `category_id`: YouTube category (default: 22)
- `privacy_status`: "private", "unlisted", or "public"
- `made_for_kids`: Boolean
- `scheduled_for`: Natural language scheduling
- `notify_subscribers`: Boolean

**Returns**:
```json
{
    "type": "youtube-upload",
    "upload_id": "uuid",
    "video_id": "YouTube_ID",
    "title": "Video Title",
    "channel_name": "Channel Name",
    "message": "Upload completed"
}
```

### 3. youtube_channels
**Purpose**: List user's YouTube channels  
**Parameters**: None

**Returns**:
```json
{
    "type": "youtube-channels",
    "channels": [
        {
            "id": "UC...",
            "name": "Channel Name",
            "statistics": {
                "subscribers": "10.5K",
                "views": "1.2M",
                "videos": "150"
            },
            "capabilities": {
                "upload": true,
                "analytics": true,
                "management": true
            }
        }
    ]
}
```

### 4. youtube_channels_enabled
**Purpose**: Check if user has connected channels  
**Parameters**: None

**Returns**:
```json
{
    "type": "youtube-channels-status",
    "enabled": true,
    "channel_count": 1,
    "message": "YouTube channels are connected"
}
```

## API Endpoints

### Authentication Endpoints

#### POST `/api/youtube/auth/initiate`
Starts OAuth flow and returns authorization URL

#### GET `/api/youtube/auth/callback`
Handles OAuth callback and token exchange

#### POST `/api/youtube/auth/refresh`
Refreshes expired access token

### Upload Endpoints

#### POST `/api/youtube/prepare-upload`
Prepares file for upload, returns reference ID

#### POST `/api/youtube/upload`
Initiates video upload to YouTube

#### GET `/api/youtube/upload/status/{upload_id}`
Returns upload progress and status

#### POST `/api/youtube/upload-thumbnail`
Uploads thumbnail for a video

### Channel Endpoints

#### GET `/api/youtube/channels`
Lists user's YouTube channels

#### GET `/api/youtube/channels/{channel_id}`
Gets specific channel details

#### DELETE `/api/youtube/channels/{channel_id}`
Removes channel connection

## Frontend Integration

### React Components

#### YouTubeAuthButton Component
```tsx
import { YouTubeAuthButton } from '@/components/youtube/YouTubeAuthButton'

function MyComponent() {
    return (
        <YouTubeAuthButton
            authUrl={authUrl}
            onSuccess={(channel) => console.log('Connected:', channel)}
            onError={(error) => console.error('Auth failed:', error)}
        />
    )
}
```

#### YouTubeUploadProgress Component
```tsx
import { YouTubeUploadProgress } from '@/components/youtube/YouTubeUploadProgress'

function UploadStatus() {
    return (
        <YouTubeUploadProgress
            uploadId={uploadId}
            onComplete={(videoId) => console.log('Uploaded:', videoId)}
        />
    )
}
```

### Zustand Store
```typescript
// stores/youtube-store.ts
interface YouTubeStore {
    channels: YouTubeChannel[]
    currentUpload: UploadSession | null
    isAuthenticating: boolean
    
    // Actions
    setChannels: (channels: YouTubeChannel[]) => void
    startUpload: (session: UploadSession) => void
    updateUploadProgress: (progress: UploadProgress) => void
    completeUpload: (videoId: string) => void
}
```

### OAuth Popup Handling
```javascript
// Handle OAuth popup communication
window.addEventListener('message', (event) => {
    if (event.data?.type === 'youtube-auth-success') {
        // Authentication successful
        const channel = event.data.channel
        // Update UI with connected channel
    }
})
```

## Database Schema

### youtube_channels Table
```sql
CREATE TABLE youtube_channels (
    id VARCHAR PRIMARY KEY,           -- YouTube channel ID
    user_id VARCHAR NOT NULL,          -- Suna user ID
    name VARCHAR NOT NULL,             -- Channel name
    custom_url VARCHAR,                -- Custom channel URL
    thumbnail_url VARCHAR,             -- Channel thumbnail
    subscriber_count BIGINT DEFAULT 0,
    view_count BIGINT DEFAULT 0,
    video_count BIGINT DEFAULT 0,
    token_data JSONB NOT NULL,        -- Encrypted OAuth tokens
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(id, user_id)
);
```

### youtube_uploads Table
```sql
CREATE TABLE youtube_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR NOT NULL,
    channel_id VARCHAR NOT NULL,
    video_id VARCHAR,                  -- YouTube video ID when complete
    title VARCHAR NOT NULL,
    description TEXT,
    tags TEXT[],
    category_id VARCHAR DEFAULT '22',
    privacy_status VARCHAR DEFAULT 'public',
    made_for_kids BOOLEAN DEFAULT FALSE,
    file_name VARCHAR NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR,
    upload_status VARCHAR NOT NULL,    -- pending, uploading, completed, failed
    upload_progress FLOAT DEFAULT 0,
    status_message TEXT,
    scheduled_for TIMESTAMP,           -- For scheduled uploads
    video_reference_id VARCHAR,        -- Reference to video file
    thumbnail_reference_id VARCHAR,    -- Reference to thumbnail
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

### video_file_references Table
```sql
CREATE TABLE video_file_references (
    id VARCHAR PRIMARY KEY,            -- 32-char reference ID
    user_id VARCHAR NOT NULL,
    file_name VARCHAR NOT NULL,
    file_path VARCHAR,                 -- Temporary storage path
    file_size BIGINT NOT NULL,
    mime_type VARCHAR,
    checksum VARCHAR,                  -- SHA256 hash
    uploaded_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,     -- Auto-cleanup time
    transcription JSONB,               -- AI transcription data
    generated_metadata JSONB,          -- AI-generated metadata
    is_temporary BOOLEAN DEFAULT TRUE
);
```

### upload_references Table
```sql
CREATE TABLE upload_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR NOT NULL,
    reference_id VARCHAR NOT NULL,     -- Links to video_file_references
    file_name VARCHAR NOT NULL,
    file_size VARCHAR,                 -- Human-readable size
    file_type VARCHAR,                 -- 'video' or 'thumbnail'
    mime_type VARCHAR,
    status VARCHAR DEFAULT 'pending',  -- pending, used
    created_at TIMESTAMP DEFAULT NOW(),
    used_at TIMESTAMP
);
```

## Configuration

### Environment Variables
```bash
# YouTube OAuth Configuration
YOUTUBE_CLIENT_ID=your_client_id_here
YOUTUBE_CLIENT_SECRET=your_client_secret_here
YOUTUBE_REDIRECT_URI=http://localhost:8000/api/youtube/auth/callback

# File Storage Configuration
YOUTUBE_FILE_STORAGE_PATH=/tmp/suna-youtube-uploads
YOUTUBE_FILE_EXPIRY_HOURS=24
YOUTUBE_MAX_FILE_SIZE=137438953472  # 128GB

# Optional: File System Uploads (Development Only)
ALLOW_FILESYSTEM_UPLOADS=false
ALLOWED_UPLOAD_PATHS=/safe/path1,/safe/path2

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_key_here
```

### Google Cloud Console Setup

1. **Create Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project or select existing
   - Note the project ID

2. **Enable APIs**
   - Enable "YouTube Data API v3"
   - Enable "YouTube Analytics API" (optional)
   - Enable "YouTube Reporting API" (optional)

3. **Create OAuth 2.0 Credentials**
   - Go to APIs & Services → Credentials
   - Create Credentials → OAuth client ID
   - Application type: Web application
   - Add authorized redirect URIs:
     - `http://localhost:8000/api/youtube/auth/callback` (development)
     - `https://your-domain.com/api/youtube/auth/callback` (production)
   - Download credentials JSON
   - Extract `client_id` and `client_secret`

4. **Configure OAuth Consent Screen**
   - Set application name and logo
   - Add scopes:
     - `youtube.upload`
     - `youtube.readonly`
     - `yt-analytics.readonly`
   - Add test users (if in testing mode)
   - Submit for verification (for production)

## Usage Examples

### Example 1: Basic Authentication and Upload

```python
# AI Agent conversation
User: "Upload my video to YouTube"

AI: "I'll help you upload your video to YouTube. First, let me check if you have any YouTube channels connected."

# Tool: youtube_channels_enabled
Response: No channels connected

AI: "I see you haven't connected a YouTube channel yet. Let me start the authentication process for you."

# Tool: youtube_authenticate
Response: Authentication URL provided

AI: "Please click the 'Authenticate with YouTube' button below to connect your YouTube account. Once connected, you'll be able to upload videos."

# User completes authentication

AI: "Great! Your YouTube channel is now connected. Please upload the video file you'd like to share on YouTube."

# User uploads video file

AI: "Perfect! I've received your video. Now I'll upload it to your YouTube channel."

# Tool: youtube_upload_video
Parameters:
{
    "channel_id": "UC123...",
    "title": "My Amazing Video",
    "description": "This is a great video about...",
    "tags": ["tutorial", "howto"],
    "privacy_status": "public"
}

AI: "Your video 'My Amazing Video' has been successfully uploaded to YouTube! It's now live at: https://youtu.be/VIDEO_ID"
```

### Example 2: Scheduled Upload

```python
User: "Schedule this video to upload tomorrow at 3pm"

# Tool: youtube_upload_video
Parameters:
{
    "channel_id": "UC123...",
    "title": "Scheduled Video",
    "description": "This will go live tomorrow",
    "scheduled_for": "tomorrow at 3pm"
}

Response:
{
    "type": "youtube-upload-scheduled",
    "scheduled_for": "2024-01-02T15:00:00Z",
    "interpretation": "tomorrow at 3:00 PM",
    "message": "Video 'Scheduled Video' scheduled for upload tomorrow at 3:00 PM"
}
```

### Example 3: Multi-Channel Management

```python
# Tool: youtube_channels
Response:
{
    "channels": [
        {
            "id": "UC123...",
            "name": "Main Channel",
            "statistics": {
                "subscribers": "50.2K",
                "views": "2.1M"
            }
        },
        {
            "id": "UC456...",
            "name": "Second Channel",
            "statistics": {
                "subscribers": "10.5K",
                "views": "500K"
            }
        }
    ]
}

User: "Upload to my Second Channel"

# Tool uses channel_id "UC456..." for upload
```

## Troubleshooting

### Common Issues and Solutions

#### 1. OAuth Configuration Error
**Error**: "YouTube OAuth is not configured"
**Solution**: 
- Verify `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` are set
- Check credentials are from correct Google Cloud project
- Ensure YouTube Data API is enabled

#### 2. Token Expired Error
**Error**: "Token is expired and no refresh token available"
**Solution**:
- User needs to re-authenticate
- Check if refresh token is being stored properly
- Verify token refresh logic is working

#### 3. Upload Fails with 403
**Error**: "403 Forbidden" during upload
**Solution**:
- Check OAuth scopes include `youtube.upload`
- Verify user has a YouTube channel
- Check channel quotas haven't been exceeded

#### 4. File Reference Not Found
**Error**: "File reference not found"
**Solution**:
- Ensure file was uploaded within 24-hour window
- Check reference ID is correct (32 characters)
- Verify user owns the file reference

#### 5. Scheduled Upload Not Processing
**Issue**: Scheduled uploads remain pending
**Solution**:
- Implement background job processor
- Check scheduled_for timestamp is correct
- Verify cron job or task queue is running

### Debug Logging

Enable detailed logging for troubleshooting:

```python
import logging

# Set logging level
logging.basicConfig(level=logging.DEBUG)

# Component-specific logging
logging.getLogger('backend.youtube').setLevel(logging.DEBUG)
logging.getLogger('backend.tools.youtube').setLevel(logging.DEBUG)
```

### Health Checks

Implement health check endpoints:

```python
# Check YouTube API connectivity
GET /api/youtube/health

# Check OAuth configuration
GET /api/youtube/health/oauth

# Check file storage
GET /api/youtube/health/storage
```

## Security Considerations

1. **Token Storage**
   - Store tokens encrypted in database
   - Use environment variables for secrets
   - Never log tokens or sensitive data

2. **File Security**
   - Validate file types and sizes
   - Scan for malware if possible
   - Clean up temporary files regularly

3. **OAuth Security**
   - Use state parameter for CSRF protection
   - Validate redirect URIs
   - Implement rate limiting

4. **API Security**
   - Authenticate all endpoints
   - Validate user ownership of resources
   - Implement request rate limiting

## Performance Optimization

1. **Upload Optimization**
   - Use resumable uploads for large files
   - Implement chunked uploads (256MB chunks)
   - Cache channel data to reduce API calls

2. **Database Optimization**
   - Index frequently queried columns
   - Implement connection pooling
   - Use batch operations where possible

3. **File Management**
   - Implement automatic cleanup job
   - Compress files if needed
   - Use CDN for thumbnail delivery

## Monitoring and Analytics

### Key Metrics to Track

1. **Authentication Metrics**
   - OAuth success rate
   - Token refresh rate
   - Authentication errors

2. **Upload Metrics**
   - Upload success rate
   - Average upload time
   - File sizes distribution
   - Failed upload reasons

3. **Usage Metrics**
   - Active users with YouTube
   - Channels per user
   - Videos uploaded per day
   - Tool usage frequency

### Monitoring Implementation

```python
# Example metrics collection
from prometheus_client import Counter, Histogram

# Define metrics
oauth_success = Counter('youtube_oauth_success', 'Successful OAuth authentications')
oauth_failure = Counter('youtube_oauth_failure', 'Failed OAuth authentications')
upload_duration = Histogram('youtube_upload_duration', 'Upload duration in seconds')
upload_size = Histogram('youtube_upload_size', 'Upload file size in bytes')
```

## Future Enhancements

1. **Planned Features**
   - Playlist management
   - Video editing (trim, add captions)
   - Live streaming support
   - Bulk uploads
   - Video analytics dashboard
   - Comment moderation tools
   - Community post creation

2. **Technical Improvements**
   - WebSocket progress updates
   - Distributed file storage
   - Video transcoding
   - Automatic retry queue
   - Enhanced scheduling options

## Support and Resources

- [YouTube Data API Documentation](https://developers.google.com/youtube/v3)
- [OAuth 2.0 for Web Server Applications](https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps)
- [YouTube API Quotas](https://developers.google.com/youtube/v3/getting-started#quota)
- [Resumable Upload Protocol](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol)

---

**Version**: 1.0.0  
**Last Updated**: January 2024  
**Maintained By**: Suna Development Team