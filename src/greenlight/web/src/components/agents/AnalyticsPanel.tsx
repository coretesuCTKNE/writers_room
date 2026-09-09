import { useCallback, useEffect, useState } from 'react';
import styled from '@emotion/styled';
import { Card, Chip } from '../index';
import { Button, ErrorText, HelperText, SectionTitle, Row, Stack } from '../layout.tsx';
import type { AgentRun, CoverageHistoryEntry, ScriptStats } from '../../lib/types';
import { MarkdownBox, agentRunResponse } from './MarkdownBox';

const Input = styled.input`
  padding: 8px 10px;
  background: var(--bg-base);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  flex: 1;
  &:focus {
    outline: none;
    border-color: var(--accent);
  }
`;

const RunRow = styled.div`
  border-bottom: 1px solid var(--bg-elevated);
`;

const RunHeader = styled.button`
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  &:hover {
    color: var(--text-primary);
  }
`;

const Caret = styled.span`
  color: var(--text-secondary);
  width: 14px;
  display: inline-block;
`;

const StatGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-top: 12px;
`;

const StatCard = styled.div`
  padding: 12px;
  background: var(--bg-elevated);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  text-align: center;
`;

const StatValue = styled.div`
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
`;

const StatLabel = styled.div`
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 4px;
`;

const CovRow = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--bg-elevated);
  font-size: 13px;
`;

const Empty = styled(HelperText)``;

const RunsToggle = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 20px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  font-weight: 600;
  padding: 0;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;

  &:hover {
    color: var(--text-primary);
  }
`;

interface AnalyticsPanelProps {
  scriptId: string;
}

export function AnalyticsPanel({ scriptId }: AnalyticsPanelProps) {
  const [stats, setStats] = useState<ScriptStats | null>(null);
  const [history, setHistory] = useState<CoverageHistoryEntry[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState('');
  const [coachResult, setCoachResult] = useState<string | null>(null);
  const [coaching, setCoaching] = useState(false);
  const [coachError, setCoachError] = useState<string | null>(null);
  const [runsOpen, setRunsOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [grafanaUrl, setGrafanaUrl] = useState('');

  useEffect(() => {
    fetch('/api/system/grafana')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setGrafanaUrl(d?.public_dashboard_url ?? ''))
      .catch(() => setGrafanaUrl(''));
  }, []);

  const toggle = (runId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) {
        next.delete(runId);
      } else {
        next.add(runId);
      }
      return next;
    });
  };

  const load = useCallback(async () => {
    setError(null);
    try {
      const [statsRes, covRes, runsRes] = await Promise.all([
        fetch(`/api/scripts/${scriptId}/analytics/stats`),
        fetch(`/api/scripts/${scriptId}/analytics/coverage?limit=5`),
        fetch(`/api/scripts/${scriptId}/agents/runs?agent=analytics`),
      ]);
      if (!statsRes.ok) throw new Error(`HTTP ${statsRes.status}`);
      setStats(await statsRes.json());
      setHistory(covRes.ok ? await covRes.json() : []);
      setRuns(runsRes.ok ? await runsRes.json() : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [scriptId]);

  useEffect(() => {
    setLoading(true);
    setStats(null);
    setHistory([]);
    void load();
  }, [load]);

  const handleCoach = async () => {
    if (!prompt.trim()) return;
    setCoaching(true);
    setCoachError(null);
    setCoachResult(null);
    try {
      const res = await fetch(`/api/scripts/${scriptId}/coach`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt.trim() }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCoachResult(data.response || '(no output)');
      await load();
    } catch (e) {
      setCoachError(e instanceof Error ? e.message : String(e));
    } finally {
      setCoaching(false);
    }
  };

  if (error) {
    return (
      <Card padding="lg">
        <SectionTitle>Analytics</SectionTitle>
        <ErrorText>{error}</ErrorText>
      </Card>
    );
  }

  return (
    <Card padding="lg">
      <SectionTitle>Story ops coach</SectionTitle>
      <HelperText>
        The analytics agent reads your goals, drafts, and scene data through the Grafana
        observability stack — ask it where you stand, what's lagging, or to mark a milestone.
      </HelperText>

      <Stack gap={8}>
        {grafanaUrl && (
          <Row gap={8}>
            <Button
              variant="secondary"
              onClick={() => window.open(grafanaUrl, '_blank', 'noopener')}
            >
              Open Story Ops dashboard ↗
            </Button>
            <HelperText>Live Grafana view: commits, goals, scenes, annotations.</HelperText>
          </Row>
        )}
        <Row gap={8}>
          <Input
            placeholder="e.g. Coach me on my progress against the goal"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !coaching && prompt.trim()) void handleCoach();
            }}
            className="analytics-panel-coach-input"
          />
          <Button variant="primary" onClick={handleCoach} disabled={coaching || !prompt.trim()}>
            {coaching ? 'Coaching…' : 'Ask the coach'}
          </Button>
        </Row>
      </Stack>

      {coachError && <ErrorText>{coachError}</ErrorText>}
      {coachResult && <MarkdownBox header="Coach:">{coachResult}</MarkdownBox>}

      {runs.length > 0 && (
        <>
          <RunsToggle
            onClick={() => setRunsOpen(!runsOpen)}
            className="analytics-panel-runs-toggle"
            aria-expanded={runsOpen}
          >
            <Caret className="analytics-panel-runs-caret">{runsOpen ? '▾' : '▸'}</Caret>
            Recent coach runs ({runs.length})
          </RunsToggle>
          {runsOpen && (
            <>
              {runs.slice(0, 10).map((r) => {
                const open = expanded.has(r.run_id);
                const body = agentRunResponse(r);
                return (
                  <RunRow key={r.run_id} className="analytics-panel-run">
                    <RunHeader className="analytics-panel-run-header" onClick={() => toggle(r.run_id)}>
                      <Caret className="analytics-panel-run-caret">{open ? '▾' : '▸'}</Caret>
                      <Chip color={r.status === 'error' ? 'danger' : 'success'}>{r.status}</Chip>
                      <span>{r.created_at}</span>
                      <span>{r.elapsed_s}s</span>
                      {r.prompt && (
                        <span
                          className="analytics-panel-run-prompt"
                          style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {r.prompt}
                        </span>
                      )}
                    </RunHeader>
                    {open && (body ? <MarkdownBox>{body}</MarkdownBox> : <HelperText>No output.</HelperText>)}
                  </RunRow>
                );
              })}
            </>
          )}
        </>
      )}

      {stats ? (
        <>
          <SectionTitle style={{ marginTop: 24 }}>Script analytics</SectionTitle>
          <HelperText>
            Live counts from the greenlight database — what the analytics agent queries.
          </HelperText>

          <StatGrid className="analytics-panel-stat-grid">
            <StatCard className="analytics-panel-stat">
              <StatValue className="analytics-panel-stat-value">{stats.scene_count}</StatValue>
              <StatLabel className="analytics-panel-stat-label">Scenes</StatLabel>
            </StatCard>
            <StatCard className="analytics-panel-stat">
              <StatValue className="analytics-panel-stat-value">{stats.character_count}</StatValue>
              <StatLabel className="analytics-panel-stat-label">Characters</StatLabel>
            </StatCard>
            <StatCard className="analytics-panel-stat">
              <StatValue className="analytics-panel-stat-value">{stats.bible_fact_count}</StatValue>
              <StatLabel className="analytics-panel-stat-label">Bible facts</StatLabel>
            </StatCard>
            <StatCard className="analytics-panel-stat">
              <StatValue className="analytics-panel-stat-value">{stats.coverage_count}</StatValue>
              <StatLabel className="analytics-panel-stat-label">Coverage runs</StatLabel>
            </StatCard>
            <StatCard className="analytics-panel-stat">
              <StatValue className="analytics-panel-stat-value">{breakdownLabel(stats, 'recommend')}</StatValue>
              <StatLabel className="analytics-panel-stat-label">RECOMMEND</StatLabel>
            </StatCard>
            <StatCard className="analytics-panel-stat">
              <StatValue className="analytics-panel-stat-value">{breakdownLabel(stats, 'consider')}</StatValue>
              <StatLabel className="analytics-panel-stat-label">CONSIDER</StatLabel>
            </StatCard>
            <StatCard className="analytics-panel-stat">
              <StatValue className="analytics-panel-stat-value">{breakdownLabel(stats, 'pass')}</StatValue>
              <StatLabel className="analytics-panel-stat-label">PASS</StatLabel>
            </StatCard>
          </StatGrid>
        </>
      ) : (
        <>
          <SectionTitle style={{ marginTop: 24 }}>Script analytics</SectionTitle>
          <HelperText>{loading ? 'Loading…' : 'No data.'}</HelperText>
        </>
      )}

      <SectionTitle style={{ marginTop: 24 }}>Coverage history</SectionTitle>
      {history.length === 0 ? (
        <Empty>No coverage runs yet.</Empty>
      ) : (
        history.map((h, i) => (
          <CovRow key={i} className="analytics-panel-cov-row">
            <Chip variant="verdict">{h.verdict}</Chip>
            <span>{h.logline}</span>
            <span style={{ marginLeft: 'auto', color: 'var(--text-secondary)' }}>
              {h.created_at}
            </span>
          </CovRow>
        ))
      )}
    </Card>
  );
}

function breakdownLabel(stats: ScriptStats, key: 'recommend' | 'consider' | 'pass'): number {
  return stats.coverage_breakdown?.[key] ?? 0;
}
