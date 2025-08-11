'use client';

import React from 'react';
import { useComposioToolkits } from '@/hooks/react-query/composio/use-composio';
import { usePipedreamAppIcon } from '@/hooks/react-query/pipedream/use-pipedream';
import {
  Calendar,
  Mail,
  HardDrive,
  Globe,
  Brain,
  FileText,
  Bot,
  Youtube,
  Instagram,
  Twitter,
  Facebook,
  Linkedin,
  Music,
  Video,
} from 'lucide-react';

interface MCPConnectionLogoProps {
  mcp: any;
  className?: string;
}

export const MCPConnectionLogo: React.FC<MCPConnectionLogoProps> = ({ mcp, className = "h-4 w-4" }) => {
  // Extract toolkit/app slug for logo fetching
  const toolkitSlug = mcp.toolkit_slug || mcp.toolkitSlug || mcp.app_slug;
  const isComposio = mcp.isComposio || mcp.customType === 'composio';
  const isPipedream = mcp.customType === 'pipedream';
  const isSocialMedia = mcp.isSocialMedia || mcp.customType === 'social-media';
  
  // Fetch Composio logo
  const { data: composioToolkits } = useComposioToolkits(
    isComposio ? toolkitSlug : undefined,
    undefined
  );
  
  // Fetch Pipedream logo
  const { data: pipedreamIconData } = usePipedreamAppIcon(
    isPipedream ? toolkitSlug : '',
    { enabled: isPipedream }
  );
  
  // Get logo URL
  let logoUrl: string | undefined;
  if (isSocialMedia && mcp.icon_url) {
    logoUrl = mcp.icon_url;
  } else if (isComposio && composioToolkits?.toolkits?.[0]) {
    logoUrl = composioToolkits.toolkits[0].logo;
  } else if (isPipedream) {
    logoUrl = pipedreamIconData?.icon_url;
  }
  
  // Fallback icon based on name
  const getFallbackIcon = () => {
    const name = (mcp.name || '').toLowerCase();
    
    // Social media platforms
    if (name.includes('youtube')) return Youtube;
    if (name.includes('instagram')) return Instagram;
    if (name.includes('twitter') || name.includes('x')) return Twitter;
    if (name.includes('facebook')) return Facebook;
    if (name.includes('linkedin')) return Linkedin;
    if (name.includes('tiktok')) return Music;
    if (name.includes('twitch')) return Video;
    
    // Other integrations
    if (name.includes('calendar')) return Calendar;
    if (name.includes('gmail') || name.includes('mail')) return Mail;
    if (name.includes('drive') || name.includes('storage')) return HardDrive;
    if (name.includes('web') || name.includes('search')) return Globe;
    if (name.includes('notion')) return Brain;
    if (name.includes('slack')) return Bot;
    return FileText;
  };
  
  const FallbackIcon = getFallbackIcon();
  
  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={mcp.name}
        className={`${className} ${isSocialMedia ? 'rounded-full object-cover' : ''}`}
        onError={(e) => {
          // Hide image and show fallback on error
          (e.target as HTMLImageElement).style.display = 'none';
        }}
      />
    );
  }
  
  return <FallbackIcon className={className} />;
};