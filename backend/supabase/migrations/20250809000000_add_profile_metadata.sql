-- Add metadata column to store YouTube channel info (username, profile pic, etc.)
BEGIN;

ALTER TABLE user_mcp_credential_profiles
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

COMMENT ON COLUMN user_mcp_credential_profiles.metadata IS 
'JSON metadata for profile-specific information like YouTube channel username, profile picture, etc.';

-- Create index for searching by metadata fields
CREATE INDEX IF NOT EXISTS idx_credential_profiles_metadata_username 
ON user_mcp_credential_profiles ((metadata->>'username'))
WHERE metadata->>'username' IS NOT NULL;

COMMIT;