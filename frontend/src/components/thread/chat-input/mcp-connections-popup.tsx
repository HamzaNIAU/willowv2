'use client';

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Cable,
  Plus,
  Search,
  Calendar,
  Mail,
  HardDrive,
  Globe,
  Brain,
  Sparkles,
  ChevronRight,
  Settings2,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { useAgentMcpConfigurations, useUpdateAgentMcpToggle } from '@/hooks/react-query/agents/use-agent-mcp-toggle';
import { toast } from 'sonner';

interface MCPConnection {
  id: string;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  connected: boolean;
  enabled: boolean;
  description?: string;
  category: 'productivity' | 'search' | 'ai' | 'system';
}

const getIconForMCP = (name: string): React.ComponentType<{ className?: string }> => {
  const lowerName = name.toLowerCase();
  if (lowerName.includes('calendar')) return Calendar;
  if (lowerName.includes('gmail') || lowerName.includes('mail')) return Mail;
  if (lowerName.includes('drive') || lowerName.includes('storage')) return HardDrive;
  if (lowerName.includes('web') || lowerName.includes('search')) return Globe;
  if (lowerName.includes('notion')) return Brain;
  return Sparkles;
};

const getCategoryForMCP = (name: string): 'productivity' | 'search' | 'ai' | 'system' => {
  const lowerName = name.toLowerCase();
  if (lowerName.includes('calendar') || lowerName.includes('notion')) return 'productivity';
  if (lowerName.includes('search') || lowerName.includes('web')) return 'search';
  if (lowerName.includes('thinking') || lowerName.includes('ai')) return 'ai';
  return 'system';
};

interface MCPConnectionsPopupProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agentId?: string;
}

export const MCPConnectionsPopup: React.FC<MCPConnectionsPopupProps> = ({
  open,
  onOpenChange,
  agentId,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const { data: mcpConfigurations = [], isLoading } = useAgentMcpConfigurations(agentId);
  const updateMcpToggle = useUpdateAgentMcpToggle();

  // Derive connections directly from mcpConfigurations without state
  const connections = React.useMemo(() => {
    if (!mcpConfigurations || mcpConfigurations.length === 0) {
      return [];
    }
    return mcpConfigurations.map((mcp: any, index: number) => ({
      id: mcp.qualifiedName || mcp.mcp_qualified_name || `${mcp.name}-${index}`,
      name: mcp.name,
      icon: getIconForMCP(mcp.name),
      connected: !!mcp.config,
      enabled: mcp.enabled !== false,
      description: mcp.description,
      category: getCategoryForMCP(mcp.name),
    }));
  }, [mcpConfigurations]);

  const handleToggle = React.useCallback(async (connectionId: string, currentEnabled: boolean) => {
    if (!agentId) {
      toast.error('No agent selected');
      return;
    }

    try {
      await updateMcpToggle.mutateAsync({
        agentId,
        mcpId: connectionId,
        enabled: !currentEnabled,
      });

      toast.success(
        `${connections.find((c) => c.id === connectionId)?.name} ${
          !currentEnabled ? 'enabled' : 'disabled'
        }`
      );
    } catch (error) {
      toast.error('Failed to update connection');
    }
  }, [agentId, connections, updateMcpToggle]);

  const filteredConnections = connections.filter((conn) => {
    const matchesSearch = conn.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || conn.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const categories = [
    { id: 'all', label: 'All', count: connections.length },
    { id: 'productivity', label: 'Productivity', count: connections.filter(c => c.category === 'productivity').length },
    { id: 'search', label: 'Search', count: connections.filter(c => c.category === 'search').length },
    { id: 'ai', label: 'AI', count: connections.filter(c => c.category === 'ai').length },
    { id: 'system', label: 'System', count: connections.filter(c => c.category === 'system').length },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] p-0 overflow-hidden">
        <div className="flex flex-col h-full">
          <DialogHeader className="px-6 pt-6 pb-4 border-b">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cable className="h-5 w-5" />
                <DialogTitle>Manage Connectors</DialogTitle>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={() => {
                  // TODO: Implement add connector functionality
                  toast.info('Add connector coming soon');
                }}
              >
                <Plus className="h-4 w-4" />
                Add connectors
              </Button>
            </div>
          </DialogHeader>

          <div className="px-6 py-3 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search connectors..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-4"
              />
            </div>
          </div>

          <div className="flex-1 overflow-hidden">
            <div className="flex h-full">
              {/* Categories sidebar */}
              <div className="w-48 border-r bg-muted/30">
                <div className="p-3">
                  {categories.map((category) => (
                    <button
                      key={category.id}
                      onClick={() => setSelectedCategory(category.id)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors ${
                        selectedCategory === category.id
                          ? 'bg-primary/10 text-primary font-medium'
                          : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <span className="capitalize">{category.label}</span>
                      <span className="text-xs opacity-60">{category.count}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Connections list */}
              <ScrollArea className="flex-1">
                <div className="p-4">
                  {isLoading ? (
                    <div className="flex items-center justify-center h-32">
                      <div className="animate-pulse text-muted-foreground">Loading connections...</div>
                    </div>
                  ) : filteredConnections.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
                      <Cable className="h-8 w-8 mb-2 opacity-50" />
                      <p className="text-sm">No connectors found</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {filteredConnections.map((connection) => {
                        const Icon = connection.icon;
                        return (
                          <div
                            key={connection.id}
                            className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                                <Icon className="h-5 w-5" />
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="font-medium text-sm">{connection.name}</span>
                                  {connection.connected ? (
                                    <div className="flex items-center gap-1 text-xs text-green-600">
                                      <CheckCircle2 className="h-3 w-3" />
                                      <span>Connected</span>
                                    </div>
                                  ) : (
                                    <button className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700">
                                      <span>Connect</span>
                                      <ChevronRight className="h-3 w-3" />
                                    </button>
                                  )}
                                </div>
                                {connection.description && (
                                  <p className="text-xs text-muted-foreground mt-0.5">
                                    {connection.description}
                                  </p>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Switch
                                checked={connection.enabled}
                                onCheckedChange={() => handleToggle(connection.id, connection.enabled)}
                                disabled={!connection.connected}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>
          </div>

          <div className="px-6 py-4 border-t bg-muted/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Sparkles className="h-4 w-4" />
                <span>Extended thinking</span>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="mt-3">
              <Button
                variant="ghost"
                size="sm"
                className="gap-2 text-muted-foreground hover:text-foreground"
                onClick={() => {
                  // TODO: Implement use style functionality
                  toast.info('Style settings coming soon');
                }}
              >
                <Settings2 className="h-4 w-4" />
                Use style
                <ChevronRight className="h-3 w-3" />
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};