'use client';

import React from 'react';
import { 
  Zap
} from 'lucide-react';
import { ComposioConnectionsSection } from '../../../../components/agents/composio/composio-connections-section';
import { PageHeader } from '@/components/ui/page-header';

export default function AppProfilesPage() {
  // Integrations should be available regardless of custom_agents flag
  return (
    <div className="container mx-auto max-w-4xl px-6 py-6">
      <div className="space-y-8">
        <PageHeader icon={Zap}>
          <span className="text-primary">App Credentials</span>
        </PageHeader>
        <ComposioConnectionsSection />
      </div>
    </div>
  );
} 