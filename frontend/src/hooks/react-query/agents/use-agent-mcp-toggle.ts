import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAgent } from './use-agents';
import { useComposioCredentialsProfiles } from '../composio/use-composio-profiles';
import { backendApi } from '@/lib/api-client';
import { toast } from 'sonner';

interface UpdateMcpToggleParams {
  agentId: string;
  mcpId: string;
  enabled: boolean;
}

export const useUpdateAgentMcpToggle = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ agentId, mcpId, enabled }: UpdateMcpToggleParams) => {
      // For now, just return success since we're only toggling UI state
      // The actual API integration would need to be implemented based on your backend
      console.log('Toggle MCP:', { agentId, mcpId, enabled });
      
      // Simulate success
      return { success: true, mcpId, enabled };
    },
    onSuccess: (data, variables) => {
      // Invalidate relevant queries to refresh the data
      queryClient.invalidateQueries({ queryKey: ['agent', variables.agentId] });
      queryClient.invalidateQueries({ queryKey: ['composio-credentials-profiles'] });
      
      // Show success message
      toast.success(`${variables.enabled ? 'Enabled' : 'Disabled'} successfully`);
    },
    onError: (error) => {
      console.error('Failed to update MCP toggle:', error);
      toast.error('Failed to update connection');
    },
  });
};

// Hook to get YouTube channels
const useYouTubeChannels = () => {
  return useQuery({
    queryKey: ['youtube', 'channels'],
    queryFn: async () => {
      try {
        const response = await backendApi.get<{ success: boolean; channels: any[] }>(
          '/youtube/channels'
        );
        return response.data.channels || [];
      } catch (error) {
        console.error('Failed to fetch YouTube channels:', error);
        return [];
      }
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

// Hook to get MCP configurations for an agent
export const useAgentMcpConfigurations = (agentId?: string) => {
  // Always call the hook with a value (empty string if no agentId)
  // The useAgent hook internally checks for valid agentId
  const { data: agent, isLoading: agentLoading, error: agentError } = useAgent(agentId || '');
  const { data: composioProfiles, isLoading: composioLoading } = useComposioCredentialsProfiles();
  const { data: youtubeChannels, isLoading: youtubeLoading } = useYouTubeChannels();
  
  const shouldFetch = !!agentId;
  
  // Extract MCP configurations from agent data
  // The agent stores MCPs in 'configured_mcps' field
  const mcpConfigurations = React.useMemo(() => {
    const allMcps = [];
    
    // Add YouTube channels as social media MCPs
    if (youtubeChannels && youtubeChannels.length > 0) {
      youtubeChannels.forEach((channel: any) => {
        allMcps.push({
          name: channel.username || channel.name,
          qualifiedName: `social.youtube.${channel.id}`,
          enabled: true, // Enabled by default if channel exists
          isSocialMedia: true,
          customType: 'social-media',
          platform: 'youtube',
          config: {
            channel_id: channel.id,
            channel_name: channel.name,
            username: channel.username,
            profile_picture: channel.profile_picture_medium || channel.profile_picture,
            mcp_url: 'http://localhost:8000/api/youtube/mcp/stream',
          },
          icon_url: channel.profile_picture_medium || channel.profile_picture,
          profile_picture: channel.profile_picture_medium || channel.profile_picture,
        });
      });
    }
    
    // Get Composio profiles and convert them to MCP format
    if (composioProfiles && composioProfiles.length > 0) {
      const composioMcps = composioProfiles.map((profile: any) => {
        // Extract the app name properly
        const appSlug = profile.toolkit_slug || profile.app_slug || '';
        const appName = profile.toolkit_name || profile.app_name || appSlug || 'Unknown';
        
        return {
          name: appName.charAt(0).toUpperCase() + appName.slice(1), // Capitalize first letter
          qualifiedName: `composio.${appSlug}`,
          enabled: true, // Enabled by default if profile exists
          isComposio: true,
          customType: 'composio',
          config: {
            profile_id: profile.profile_id,
            profile_name: profile.profile_name,
          },
          selectedProfileId: profile.profile_id,
          toolkit_slug: appSlug,
          toolkitSlug: appSlug, // Add both variations
          app_slug: appSlug,
        };
      });
      allMcps.push(...composioMcps);
    }
    
    // Also get MCPs from agent configuration if available
    if (shouldFetch && agent) {
      const configured = agent.configured_mcps || agent.mcp_configurations || [];
      const custom = agent.custom_mcps || [];
      
      // Extract other non-Composio MCPs
      const otherMcps = configured
        .filter((mcp: any) => !(mcp.customType === 'composio' || mcp.isComposio || (mcp.qualifiedName && mcp.qualifiedName.startsWith('composio.'))))
        .concat(custom);
      
      allMcps.push(...otherMcps);
    }
    
    return allMcps;
  }, [shouldFetch, agent, composioProfiles]);
  
  return React.useMemo(() => ({
    data: mcpConfigurations,
    isLoading: shouldFetch ? (agentLoading || composioLoading || youtubeLoading) : (composioLoading || youtubeLoading),
    error: shouldFetch ? agentError : null,
  }), [mcpConfigurations, agentLoading, composioLoading, youtubeLoading, agentError, shouldFetch]);
};