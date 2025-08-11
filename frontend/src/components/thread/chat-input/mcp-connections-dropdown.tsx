'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import {
  Cable,
  Search,
  Settings2,
  ChevronRight,
  Youtube,
  Instagram,
  Twitter,
  Facebook,
  Linkedin,
  Music,
  Video,
} from 'lucide-react';
import { useAgentMcpConfigurations, useUpdateAgentMcpToggle } from '@/hooks/react-query/agents/use-agent-mcp-toggle';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { MCPConnectionLogo } from './mcp-connection-logo';

interface MCPConnectionsDropdownProps {
  agentId?: string;
  disabled?: boolean;
}

export const MCPConnectionsDropdown: React.FC<MCPConnectionsDropdownProps> = ({
  agentId,
  disabled = false,
}) => {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [localToggles, setLocalToggles] = useState<Record<string, boolean>>({});
  const dropdownRef = useRef<HTMLDivElement>(null);
  
  const { data: mcpConfigurations = [], isLoading } = useAgentMcpConfigurations(agentId);
  const updateMcpToggle = useUpdateAgentMcpToggle();
  
  // Initialize local toggles from MCP configurations
  React.useEffect(() => {
    const initialToggles: Record<string, boolean> = {};
    mcpConfigurations.forEach((mcp: any) => {
      const mcpId = mcp.qualifiedName || mcp.mcp_qualified_name || `${mcp.name}`;
      initialToggles[mcpId] = mcp.enabled !== false;
    });
    setLocalToggles(initialToggles);
  }, [mcpConfigurations]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  const handleToggle = React.useCallback(async (mcpId: string) => {
    // Update local state immediately for responsive UI
    const currentEnabled = localToggles[mcpId] ?? true;
    const newEnabled = !currentEnabled;
    
    setLocalToggles(prev => ({
      ...prev,
      [mcpId]: newEnabled
    }));

    // If agent is selected, persist the change
    if (agentId) {
      try {
        await updateMcpToggle.mutateAsync({
          agentId,
          mcpId,
          enabled: newEnabled,
        });
      } catch (error) {
        // Revert on error
        setLocalToggles(prev => ({
          ...prev,
          [mcpId]: currentEnabled
        }));
      }
    }
  }, [agentId, updateMcpToggle, localToggles]);

  const filteredMcpConfigs = mcpConfigurations.filter((mcp: any) =>
    mcp.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Separate social media MCPs from Composio integrations
  const socialMediaMcps = filteredMcpConfigs.filter((mcp: any) => mcp.isSocialMedia || mcp.customType === 'social-media');
  const composioMcps = filteredMcpConfigs.filter((mcp: any) => mcp.isComposio || mcp.customType === 'composio');
  const otherMcps = filteredMcpConfigs.filter((mcp: any) => 
    !mcp.isSocialMedia && !mcp.isComposio && mcp.customType !== 'social-media' && mcp.customType !== 'composio'
  );

  // Group social media by platform
  const socialMediaByPlatform = socialMediaMcps.reduce((acc: any, mcp: any) => {
    const platform = mcp.platform || 'other';
    if (!acc[platform]) acc[platform] = [];
    acc[platform].push(mcp);
    return acc;
  }, {});

  const connectedCount = mcpConfigurations.filter((mcp: any) => mcp.enabled !== false).length;

  return (
    <div className="relative" ref={dropdownRef}>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className={cn(
          "h-8 w-8 rounded-lg p-0 hover:bg-accent",
          isOpen && "bg-accent"
        )}
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
      >
        <Cable className="h-4 w-4" />
      </Button>

      {isOpen && (
        <div className="absolute bottom-full mb-2 left-0 w-[320px] rounded-lg border bg-popover p-0 shadow-lg animate-in fade-in-0 zoom-in-95">
          {/* Search */}
          <div className="p-3 pb-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search menu"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 pl-8 text-sm"
              />
            </div>
          </div>


          {/* MCP Connections */}
          <div className="max-h-[300px] overflow-y-auto">
            {isLoading ? (
              <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                Loading connections...
              </div>
            ) : filteredMcpConfigs.length === 0 ? (
              <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                No connections available
              </div>
            ) : (
              <div className="pb-2">
                {/* Social Media Sections by Platform */}
                {Object.keys(socialMediaByPlatform).length > 0 && (
                  <>
                    {socialMediaByPlatform.youtube && (
                      <>
                        <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                          <Youtube className="h-3 w-3" />
                          YouTube
                        </div>
                        <div className="px-3 pb-2">
                          {socialMediaByPlatform.youtube.map((mcp: any, index: number) => {
                            const displayName = mcp.name || 'Unknown';
                            const mcpId = mcp.qualifiedName || `${displayName}-${index}`;
                            const isEnabled = localToggles[mcpId] ?? (mcp.enabled !== false);
                            const isConnected = !!mcp.config;
                            
                            const profilePicture = mcp.profile_picture || mcp.config?.profile_picture || mcp.icon_url;
                            
                            return (
                              <div
                                key={mcpId}
                                className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-accent"
                              >
                                <div className="flex items-center gap-2">
                                  {profilePicture ? (
                                    <>
                                      <img
                                        src={profilePicture}
                                        alt={displayName}
                                        className="h-5 w-5 rounded-full object-cover border border-border/50"
                                        onError={(e) => {
                                          console.log('Failed to load profile picture for:', displayName, profilePicture);
                                          (e.target as HTMLImageElement).style.display = 'none';
                                          (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                                        }}
                                      />
                                      <Youtube className="h-5 w-5 text-red-600 hidden" />
                                    </>
                                  ) : (
                                    <Youtube className="h-5 w-5 text-red-600" />
                                  )}
                                  <span className="text-sm">{displayName}</span>
                                </div>
                                {isConnected ? (
                                  <Switch
                                    checked={isEnabled}
                                    onCheckedChange={() => handleToggle(mcpId)}
                                    className="scale-90"
                                  />
                                ) : (
                                  <button
                                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                                    onClick={() => {
                                      router.push('/social-media');
                                      setIsOpen(false);
                                    }}
                                  >
                                    Connect
                                    <ChevronRight className="h-3 w-3" />
                                  </button>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </>
                    )}
                    
                    {/* Add other social media platforms here in the future */}
                    {socialMediaByPlatform.instagram && (
                      <>
                        <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                          <Instagram className="h-3 w-3" />
                          Instagram
                        </div>
                        <div className="px-3 pb-2">
                          {/* Instagram accounts will go here */}
                        </div>
                      </>
                    )}
                    
                    {(composioMcps.length > 0 || otherMcps.length > 0) && (
                      <Separator className="my-2" />
                    )}
                  </>
                )}
                
                {/* Composio Integrations Section */}
                {composioMcps.length > 0 && (
                  <>
                    <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground">Integrations</div>
                    <div className="px-3 pb-2">
                      {composioMcps.map((mcp: any, index: number) => {
                        const displayName = mcp.name || mcp.toolkit_slug || mcp.toolkitSlug || 'Unknown';
                        const mcpId = mcp.qualifiedName || mcp.mcp_qualified_name || `${displayName}-${index}`;
                        const isEnabled = localToggles[mcpId] ?? (mcp.enabled !== false);
                        const isConnected = mcp.selectedProfileId || mcp.config?.profile_id || !!mcp.config;
                        
                        return (
                          <div
                            key={mcpId}
                            className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-accent"
                          >
                            <div className="flex items-center gap-2">
                              <MCPConnectionLogo mcp={mcp} className="h-4 w-4" />
                              <span className="text-sm capitalize">{displayName}</span>
                            </div>
                            {isConnected ? (
                              <Switch
                                checked={isEnabled}
                                onCheckedChange={() => handleToggle(mcpId)}
                                className="scale-90"
                              />
                            ) : (
                              <button
                                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                                onClick={() => {
                                  router.push('/settings/credentials');
                                  setIsOpen(false);
                                }}
                              >
                                Connect
                                <ChevronRight className="h-3 w-3" />
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    {otherMcps.length > 0 && (
                      <Separator className="my-2" />
                    )}
                  </>
                )}
                
                {/* Other MCPs */}
                {otherMcps.length > 0 && (
                  <div className="px-3 pb-2">
                    {otherMcps.map((mcp: any, index: number) => {
                      const displayName = mcp.name || 'Unknown';
                      const mcpId = mcp.qualifiedName || `${displayName}-${index}`;
                      const isEnabled = localToggles[mcpId] ?? (mcp.enabled !== false);
                      const isConnected = !!mcp.config;
                      
                      return (
                        <div
                          key={mcpId}
                          className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-accent"
                        >
                          <div className="flex items-center gap-2">
                            <MCPConnectionLogo mcp={mcp} className="h-4 w-4" />
                            <span className="text-sm capitalize">{displayName}</span>
                          </div>
                          {isConnected ? (
                            <Switch
                              checked={isEnabled}
                              onCheckedChange={() => handleToggle(mcpId)}
                              className="scale-90"
                            />
                          ) : (
                            <button
                              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                              onClick={() => {
                                toast.info('Connect feature coming soon');
                              }}
                            >
                              Connect
                              <ChevronRight className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Manage connectors links */}
          <div className="border-t px-3 py-2 mt-2 space-y-1">
            <button
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
              onClick={() => {
                setIsOpen(false);
                router.push('/social-media');
              }}
            >
              <Settings2 className="h-3.5 w-3.5" />
              Manage social media
            </button>
            <button
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
              onClick={() => {
                setIsOpen(false);
                router.push('/settings/credentials');
              }}
            >
              <Settings2 className="h-3.5 w-3.5" />
              Manage integrations
            </button>
          </div>
        </div>
      )}
    </div>
  );
};