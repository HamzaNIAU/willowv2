/**
 * YouTube Upload Handler
 * Handles video file uploads for YouTube integration
 */

import { toast } from 'sonner';
import { createClient } from '@/lib/supabase/client';

const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || '';

// Video file extensions supported by YouTube
const VIDEO_EXTENSIONS = [
  '.mp4', '.mov', '.avi', '.wmv', '.flv', '.3gpp', '.webm', '.mkv', '.m4v', '.mpg', '.mpeg'
];

const VIDEO_MIME_TYPES = [
  'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-ms-wmv', 
  'video/x-flv', 'video/3gpp', 'video/webm', 'video/x-matroska', 
  'video/x-m4v', 'video/mpeg'
];

// Maximum file size for YouTube (128GB)
const MAX_VIDEO_SIZE = 128 * 1024 * 1024 * 1024;

export interface YouTubeUploadReference {
  referenceId: string;
  fileName: string;
  fileSize: string;
  expiresAt: string;
  isVideo: boolean;
}

/**
 * Check if a file is a video file supported by YouTube
 */
export function isVideoFile(file: File): boolean {
  // Check MIME type
  if (VIDEO_MIME_TYPES.includes(file.type)) {
    return true;
  }
  
  // Check file extension as fallback
  const fileName = file.name.toLowerCase();
  return VIDEO_EXTENSIONS.some(ext => fileName.endsWith(ext));
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

/**
 * Prepare a video file for YouTube upload
 * Creates a reference that can be used by the AI agent
 */
export async function prepareYouTubeUpload(
  file: File,
  fileType: 'video' | 'thumbnail' = 'video'
): Promise<YouTubeUploadReference | null> {
  try {
    // Validate file size
    if (file.size > MAX_VIDEO_SIZE) {
      toast.error(`File size exceeds YouTube's 128GB limit: ${file.name}`);
      return null;
    }

    // Create form data
    const formData = new FormData();
    formData.append('file', file);
    formData.append('file_type', fileType);

    // Get auth token
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session?.access_token) {
      toast.error('Please sign in to upload videos');
      return null;
    }

    // Upload to YouTube prepare endpoint
    const response = await fetch(`${API_URL}/youtube/prepare-upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${session.access_token}`,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || 'Failed to prepare upload');
    }

    const data = await response.json();
    
    toast.success(
      fileType === 'video' 
        ? `Video prepared for YouTube upload: ${file.name}`
        : `Thumbnail prepared: ${file.name}`
    );

    return {
      referenceId: data.reference_id,
      fileName: data.file_name,
      fileSize: data.file_size,
      expiresAt: data.expires_at,
      isVideo: fileType === 'video',
    };
    
  } catch (error) {
    console.error('Failed to prepare YouTube upload:', error);
    toast.error(`Failed to prepare ${fileType} for upload: ${error instanceof Error ? error.message : 'Unknown error'}`);
    return null;
  }
}

/**
 * Handle video files for YouTube upload
 * This can be called when video files are detected in regular file uploads
 */
export async function handleYouTubeVideoUpload(
  files: File[],
  onUploadPrepared?: (references: YouTubeUploadReference[]) => void
): Promise<YouTubeUploadReference[]> {
  const videoFiles = files.filter(isVideoFile);
  const references: YouTubeUploadReference[] = [];

  if (videoFiles.length === 0) {
    return references;
  }

  // Notify user about YouTube video detection
  toast.info(
    `Detected ${videoFiles.length} video file${videoFiles.length > 1 ? 's' : ''} for YouTube upload`
  );

  // Process each video file
  for (const file of videoFiles) {
    const reference = await prepareYouTubeUpload(file, 'video');
    if (reference) {
      references.push(reference);
    }
  }

  // Callback with prepared references
  if (onUploadPrepared && references.length > 0) {
    onUploadPrepared(references);
  }

  return references;
}

/**
 * Enhanced drag and drop handler that detects YouTube videos
 */
export async function handleEnhancedDrop(
  e: React.DragEvent<HTMLDivElement>,
  originalHandler: (files: File[]) => void,
  onYouTubeVideos?: (references: YouTubeUploadReference[]) => void
) {
  e.preventDefault();
  e.stopPropagation();

  const files = Array.from(e.dataTransfer.files);
  
  // Separate video files from other files
  const videoFiles = files.filter(isVideoFile);
  const otherFiles = files.filter(file => !isVideoFile(file));

  // Handle regular files with original handler
  if (otherFiles.length > 0) {
    originalHandler(otherFiles);
  }

  // Handle YouTube videos
  if (videoFiles.length > 0) {
    // Ask user if they want to prepare for YouTube
    const shouldPrepareForYouTube = await new Promise<boolean>((resolve) => {
      // You could show a dialog here, for now we'll auto-detect
      const hasYouTubeKeywords = [
        'youtube', 'upload', 'video'
      ].some(keyword => 
        window.location.href.includes(keyword) || 
        document.body.textContent?.toLowerCase().includes(keyword)
      );
      
      resolve(hasYouTubeKeywords || videoFiles.length > 0);
    });

    if (shouldPrepareForYouTube) {
      const references = await handleYouTubeVideoUpload(videoFiles, onYouTubeVideos);
      
      if (references.length > 0) {
        // Add a message to indicate videos are ready for YouTube
        const videoList = references.map(r => r.fileName).join(', ');
        toast.success(
          `Video${references.length > 1 ? 's' : ''} ready for YouTube upload: ${videoList}`,
          {
            duration: 5000,
            description: 'You can now ask the AI to upload to YouTube',
          }
        );
      }
    } else {
      // Handle as regular files
      originalHandler(videoFiles);
    }
  }
}

/**
 * Component to show YouTube upload status in chat
 */
export function YouTubeUploadIndicator({ 
  references 
}: { 
  references: YouTubeUploadReference[] 
}) {
  if (references.length === 0) return null;

  return (
    <div className="flex items-center gap-2 p-2 bg-red-50 dark:bg-red-900/20 rounded-lg text-sm">
      <svg className="w-5 h-5 text-red-600" fill="currentColor" viewBox="0 0 24 24">
        <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
      </svg>
      <span className="text-red-600 dark:text-red-400 font-medium">
        {references.length} video{references.length > 1 ? 's' : ''} ready for YouTube
      </span>
    </div>
  );
}