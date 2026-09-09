import styled from '@emotion/styled';
import { useCallback, useEffect } from 'react';
import { useAgentStore } from '../lib/store-agent';
import { useProjectStore } from '../lib/store-project';
import { useAgentWebSocket } from '../lib/useAgentWebSocket';
import { ScriptPicker } from './ScriptPicker';
import { ShellTopBar } from './ShellTopBar';
import { SidebarNav } from './SidebarNav';

const Layout = styled.div`
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
`;

const Body = styled.div`
  display: flex;
  flex: 1;
  overflow: hidden;
`;

const MainPane = styled.main`
  flex: 1;
  overflow-y: auto;
  padding: 6px;
  background: var(--bg-base);
`;

interface ShellProps {
  children: React.ReactNode;
}

export function Shell({ children }: ShellProps) {
  const updateAgent = useAgentStore((s) => s.updateAgent);
  const session = useProjectStore((s) => s.session);
  const refreshSession = useProjectStore((s) => s.refreshSession);
  const loadScripts = useProjectStore((s) => s.loadScripts);

  useEffect(() => {
    refreshSession();
    loadScripts();
  }, [refreshSession, loadScripts]);

  const handleAgentEvent = useCallback(
    (data: { agent: string; status: 'idle' | 'running' | 'completed' | 'error'; message?: string }) => {
      updateAgent(data.agent, {
        status: data.status,
        lastEvent: data.message || undefined,
      });
    },
    [updateAgent],
  );

  useAgentWebSocket(handleAgentEvent);

  return (
    <Layout className="app-shell">
      <ShellTopBar>
        <ScriptPicker session={session} />
      </ShellTopBar>
      <Body className="app-shell-body">
        <SidebarNav />
        <MainPane className="app-shell-main">{children}</MainPane>
      </Body>
    </Layout>
  );
}
