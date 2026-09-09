import styled from '@emotion/styled';
import { useAgentStore } from '../lib/store-agent';

const TopBar = styled.header`
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 20px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--bg-elevated);
  flex-shrink: 0;
`;

const Logo = styled.div`
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 1px;
`;

const ContextLabel = styled.div`
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-secondary);
`;

const Spacer = styled.div`
  flex: 1;
`;

const RightGroup = styled.div`
  display: flex;
  align-items: center;
  gap: 14px;
`;

const AgentStatus = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
`;

const AgentDot = styled.div<{ status: string }>`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: ${({ status }) =>
    status === 'running' ? 'var(--accent)' :
    status === 'error' ? 'var(--danger)' :
    'var(--bg-elevated)'};
  transition: background var(--transition);
`;

interface ShellTopBarProps {
  children?: React.ReactNode;
}

export function ShellTopBar({ children }: ShellTopBarProps) {
  const agents = useAgentStore((s) => s.agents);

  return (
    <TopBar className="app-topbar">
      <Logo className="app-topbar-logo">WRITERS ROOM GREENLIGHT</Logo>
      <Spacer />
      <AgentStatus className="app-topbar-agent-status">
        {Object.values(agents).map((agent) => (
          <AgentDot
            key={agent.name}
            status={agent.status}
            title={`${agent.name}: ${agent.status}`}
            className={`app-topbar-agent-dot app-topbar-agent-dot--${agent.status}`}
          />
        ))}
      </AgentStatus>
      <RightGroup className="app-topbar-right-group">
        <ContextLabel className="app-topbar-label">Active Screenplay</ContextLabel>
        {children}
      </RightGroup>
    </TopBar>
  );
}
