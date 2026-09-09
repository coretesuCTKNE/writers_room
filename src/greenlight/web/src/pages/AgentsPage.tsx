import { Card, Chip } from '../components';
import { BiblePanel } from '../components/agents/BiblePanel';
import { AnalyticsPanel } from '../components/agents/AnalyticsPanel';
import { RewritePanel } from '../components/agents/RewritePanel';
import { ShowrunnerPanel } from '../components/agents/ShowrunnerPanel';
import {
  PageContainer,
  PageTitle,
  SectionTitle,
  Stack,
  HelperText,
} from '../components/layout.tsx';
import { useAgentStore } from '../lib/store-agent';
import { useProjectStore } from '../lib/store-project';

const AGENT_STATUS_ROWS: Array<{ name: string; label: string }> = [
  { name: 'bible', label: 'Bible' },
  { name: 'analytics', label: 'Analytics' },
  { name: 'rewrite', label: 'Rewrite' },
  { name: 'showrunner', label: 'Showrunner' },
];

const statusColor = (
  status: string,
): 'success' | 'warn' | 'danger' | 'accent' | 'neutral' =>
  status === 'completed'
    ? 'success'
    : status === 'running'
      ? 'warn'
      : status === 'error'
        ? 'danger'
        : 'neutral';

export function AgentsPage() {
  const session = useProjectStore((s) => s.session);
  const agents = useAgentStore((s) => s.agents);

  if (!session?.loaded) {
    return (
      <PageContainer className="agent-room-page">
        <PageTitle className="agent-room-page-title">Agent Room</PageTitle>
        <Card padding="lg" className="agent-room-empty-card">
          <HelperText>
            No screenplay loaded. Load one from the sidebar to inspect agent work.
          </HelperText>
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer className="agent-room-page">
      <PageTitle className="agent-room-page-title">Agent Room</PageTitle>

      <SectionTitle className="agent-room-status-title">Agent status</SectionTitle>
      <Stack direction="row" gap={8} style={{ marginBottom: 24 }} className="agent-room-status-row">
        {AGENT_STATUS_ROWS.map(({ name, label }) => {
          const st = agents[name]?.status ?? 'idle';
          return (
            <Chip key={name} color={statusColor(st)}>
              {label}: {st}
            </Chip>
          );
        })}
      </Stack>

      <Stack gap={16} className="agent-room-panels">
        <section className="agent-room-panel-section">
          <SectionTitle className="agent-room-panel-title">Showrunner</SectionTitle>
          <ShowrunnerPanel scriptId={session.scriptId} />
        </section>

        <section className="agent-room-panel-section">
          <SectionTitle className="agent-room-panel-title">Continuity — Story Bible</SectionTitle>
          <BiblePanel scriptId={session.scriptId} />
        </section>

        <section className="agent-room-panel-section">
          <SectionTitle className="agent-room-panel-title">Analytics</SectionTitle>
          <AnalyticsPanel scriptId={session.scriptId} />
        </section>

        <section className="agent-room-panel-section">
          <SectionTitle className="agent-room-panel-title">Rewrite</SectionTitle>
          <RewritePanel scriptId={session.scriptId} />
        </section>
      </Stack>
    </PageContainer>
  );
}
