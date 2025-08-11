'use client';

import React from 'react';
import { Bot } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface AgentSelectorProps {
  threadId?: string;
  isGenerating?: boolean;
}

export function AgentSelector({ threadId, isGenerating }: AgentSelectorProps) {
  // Always show the default Suna agent
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 rounded-lg">
      <div className="p-1.5 bg-amber-500/10 rounded-lg">
        <span className="text-lg">🌞</span>
      </div>
      <div className="flex flex-col">
        <span className="text-sm font-medium">Suna</span>
        <span className="text-xs text-muted-foreground">AI Assistant</span>
      </div>
    </div>
  );
}