-- YouTube Integration Tables

BEGIN;

-- YouTube channels table - stores authenticated YouTube channels
CREATE TABLE IF NOT EXISTS youtube_channels (
    id VARCHAR PRIMARY KEY,                  -- YouTube channel ID (UC...)
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,                   -- Channel name/title
    username VARCHAR,                         -- YouTube @handle
    custom_url VARCHAR,                      -- Custom channel URL
    profile_picture VARCHAR,                 -- Channel profile picture URL
    profile_picture_medium VARCHAR,          -- Medium size profile pic
    profile_picture_small VARCHAR,           -- Small size profile pic
    description TEXT,                        -- Channel description
    subscriber_count BIGINT DEFAULT 0,       -- Subscriber count
    view_count BIGINT DEFAULT 0,             -- Total view count
    video_count BIGINT DEFAULT 0,            -- Total video count
    country VARCHAR,                         -- Channel country
    published_at TIMESTAMP,                  -- Channel creation date
    
    -- OAuth tokens (encrypted)
    access_token TEXT NOT NULL,              -- Encrypted access token
    refresh_token TEXT,                      -- Encrypted refresh token
    token_expires_at TIMESTAMP NOT NULL,     -- Token expiration time
    token_scopes TEXT[],                     -- OAuth scopes granted
    
    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    
    UNIQUE(id, user_id)
);

-- YouTube uploads tracking table
CREATE TABLE IF NOT EXISTS youtube_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    channel_id VARCHAR NOT NULL REFERENCES youtube_channels(id) ON DELETE CASCADE,
    video_id VARCHAR,                        -- YouTube video ID when complete
    title VARCHAR NOT NULL,
    description TEXT,
    tags TEXT[],
    category_id VARCHAR DEFAULT '22',        -- YouTube category ID
    privacy_status VARCHAR DEFAULT 'public', -- public, unlisted, private
    made_for_kids BOOLEAN DEFAULT FALSE,
    
    -- File information
    file_name VARCHAR NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR,
    
    -- Upload status
    upload_status VARCHAR NOT NULL,          -- pending, uploading, completed, failed
    upload_progress FLOAT DEFAULT 0,         -- Progress percentage
    status_message TEXT,                     -- Status or error message
    
    -- Scheduling
    scheduled_for TIMESTAMP,                 -- For scheduled uploads
    notify_subscribers BOOLEAN DEFAULT TRUE,
    
    -- References
    video_reference_id VARCHAR,              -- Reference to video file
    thumbnail_reference_id VARCHAR,          -- Reference to thumbnail
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Video file references for temporary storage
CREATE TABLE IF NOT EXISTS video_file_references (
    id VARCHAR PRIMARY KEY,                  -- 32-char reference ID
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    file_name VARCHAR NOT NULL,
    file_path VARCHAR,                       -- Temporary storage path
    file_size BIGINT NOT NULL,
    mime_type VARCHAR,
    checksum VARCHAR,                        -- SHA256 hash
    
    -- AI-generated metadata
    transcription JSONB,                     -- AI transcription data
    generated_metadata JSONB,                -- AI-generated titles, descriptions
    
    -- Management
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, -- Auto-cleanup time
    is_temporary BOOLEAN DEFAULT TRUE
);

-- Upload references queue
CREATE TABLE IF NOT EXISTS upload_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    reference_id VARCHAR NOT NULL,           -- Links to video_file_references
    file_name VARCHAR NOT NULL,
    file_size VARCHAR,                       -- Human-readable size
    file_type VARCHAR,                       -- 'video' or 'thumbnail'
    mime_type VARCHAR,
    status VARCHAR DEFAULT 'pending',        -- pending, used, expired
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    used_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_youtube_channels_user_id ON youtube_channels(user_id);
CREATE INDEX idx_youtube_channels_is_active ON youtube_channels(is_active);
CREATE INDEX idx_youtube_uploads_user_id ON youtube_uploads(user_id);
CREATE INDEX idx_youtube_uploads_channel_id ON youtube_uploads(channel_id);
CREATE INDEX idx_youtube_uploads_status ON youtube_uploads(upload_status);
CREATE INDEX idx_video_file_references_user_id ON video_file_references(user_id);
CREATE INDEX idx_video_file_references_expires_at ON video_file_references(expires_at);
CREATE INDEX idx_upload_references_user_id ON upload_references(user_id);
CREATE INDEX idx_upload_references_status ON upload_references(status);

-- Row Level Security
ALTER TABLE youtube_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE youtube_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_file_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE upload_references ENABLE ROW LEVEL SECURITY;

-- RLS Policies for youtube_channels
CREATE POLICY "Users can view their own YouTube channels"
    ON youtube_channels FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own YouTube channels"
    ON youtube_channels FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own YouTube channels"
    ON youtube_channels FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own YouTube channels"
    ON youtube_channels FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for youtube_uploads
CREATE POLICY "Users can view their own uploads"
    ON youtube_uploads FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own uploads"
    ON youtube_uploads FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own uploads"
    ON youtube_uploads FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own uploads"
    ON youtube_uploads FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for video_file_references
CREATE POLICY "Users can view their own file references"
    ON video_file_references FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own file references"
    ON video_file_references FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own file references"
    ON video_file_references FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own file references"
    ON video_file_references FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for upload_references
CREATE POLICY "Users can view their own upload references"
    ON upload_references FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own upload references"
    ON upload_references FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own upload references"
    ON upload_references FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own upload references"
    ON upload_references FOR DELETE
    USING (auth.uid() = user_id);

-- Functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_youtube_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_youtube_channels_updated_at
    BEFORE UPDATE ON youtube_channels
    FOR EACH ROW
    EXECUTE FUNCTION update_youtube_updated_at();

COMMIT;