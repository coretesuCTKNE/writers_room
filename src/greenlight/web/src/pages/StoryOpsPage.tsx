import { useEffect, useMemo, useState } from 'react';
import styled from '@emotion/styled';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, Chip } from '../components';
import {
  ErrorText,
  HelperText,
  PageContainer,
  PageTitle,
  SectionTitle,
  Stack,
} from '../components/layout.tsx';
import { useProjectStore } from '../lib/store-project';
import type { StoryOpsPayload } from '../lib/types';

const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: 16px;
`;

const ChartBox = styled.div`
  height: 240px;
`;

const StatRow = styled.div`
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
`;

const GoalTrack = styled.div`
  height: 8px;
  border-radius: 4px;
  background: var(--bg-elevated);
  overflow: hidden;
`;

const GoalFill = styled.div<{ pct: number }>`
  height: 100%;
  width: ${({ pct }) => Math.min(pct, 100)}%;
  background: ${({ pct }) => (pct >= 100 ? 'var(--success)' : pct >= 50 ? 'var(--accent)' : 'var(--warn)')};
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;

  th,
  td {
    text-align: left;
    padding: 6px 8px;
    border-bottom: 1px solid var(--bg-elevated);
  }

  th {
    color: var(--text-secondary);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.5px;
  }

  td {
    color: var(--text-primary);
  }
`;

const ChartColors = ['#32cd32', '#4a90d9', '#eab308', '#ef4444', '#a855f7', '#06b6d4', '#f97316', '#94a3b8'];

function timeShort(iso: string): string {
  const d = new Date(iso.replace(' ', 'T') + (iso.endsWith('Z') ? '' : 'Z'));
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { month: 'short', day: 'numeric' });
}

export function StoryOpsPage() {
  const session = useProjectStore((s) => s.session);
  const [data, setData] = useState<StoryOpsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session?.loaded || !session.scriptId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetch(`/api/scripts/${session.scriptId}/storyops`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [session?.loaded, session?.scriptId]);

  const commitData = useMemo(
    () =>
      (data?.commit_history ?? []).map((c) => ({
        name: timeShort(c.created_at),
        words: c.word_count,
        pages: c.page_count,
      })),
    [data],
  );

  const characterPresence = useMemo(() => {
    const counts = new Map<string, number>();
    for (const scene of data?.scene_stats ?? []) {
      for (const ch of scene.characters) {
        counts.set(ch, (counts.get(ch) ?? 0) + 1);
      }
    }
    return [...counts.entries()]
      .map(([character, scenes]) => ({ character, scenes }))
      .sort((a, b) => b.scenes - a.scenes)
      .slice(0, 12);
  }, [data]);

  const intExt = useMemo(() => {
    const counts = new Map<string, number>();
    for (const scene of data?.scene_stats ?? []) {
      const key = scene.setting || 'UNSPECIFIED';
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts.entries()].map(([name, value]) => ({ name, value }));
  }, [data]);

  const dayNight = useMemo(() => {
    const counts = new Map<string, number>();
    for (const scene of data?.scene_stats ?? []) {
      const key = scene.time_of_day || 'UNSPECIFIED';
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts.entries()].map(([name, value]) => ({ name, value }));
  }, [data]);

  if (!session?.loaded) {
    return (
      <PageContainer>
        <PageTitle>Story Ops</PageTitle>
        <Card padding="lg">
          <HelperText>No screenplay loaded. Load one from the sidebar to see its story ops.</HelperText>
        </Card>
      </PageContainer>
    );
  }

  if (loading) {
    return (
      <PageContainer>
        <PageTitle>Story Ops</PageTitle>
        <Card padding="lg">
          <HelperText>Loading story ops…</HelperText>
        </Card>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer>
        <PageTitle>Story Ops</PageTitle>
        <Card padding="lg">
          <ErrorText>{error}</ErrorText>
        </Card>
      </PageContainer>
    );
  }

  const summary = data?.summary;
  const scenes = data?.scene_stats ?? [];

  return (
    <PageContainer>
      <PageTitle>Story Ops</PageTitle>
      <HelperText>
        Live view of your draft's vitals — commits, goals, scene mix, and agent activity. The same data
        feeds the analytics coach.
      </HelperText>

      <Stack gap={16}>
        <Card padding="lg">
          <SectionTitle>Vitals</SectionTitle>
          <StatRow>
            <Chip color="accent">{summary?.scene_count ?? 0} scenes</Chip>
            <Chip color="neutral">{summary?.character_count ?? 0} characters</Chip>
            <Chip color="neutral">{summary?.bible_fact_count ?? 0} bible facts</Chip>
            <Chip color="success">{summary?.coverage_breakdown?.pass ?? 0} coverage pass</Chip>
            <Chip color="warn">{summary?.coverage_breakdown?.consider ?? 0} consider</Chip>
          </StatRow>
        </Card>

        {(data?.goals.length ?? 0) > 0 && (
          <Card padding="lg">
            <SectionTitle>Goals</SectionTitle>
            <Stack gap={12}>
              {data?.goals.map((g) => (
                <div key={g.goal_id}>
                  <StatRow>
                    <span>
                      <strong>{g.metric}</strong> — {g.current.toLocaleString()} / {g.target.toLocaleString()}
                      {g.days_left !== null && ` · ${g.days_left}d left`}
                    </span>
                    <Chip color={g.pct >= 100 ? 'success' : g.pct >= 50 ? 'accent' : 'warn'}>
                      {g.pct.toFixed(0)}%
                    </Chip>
                  </StatRow>
                  <GoalTrack>
                    <GoalFill pct={g.pct} />
                  </GoalTrack>
                </div>
              ))}
            </Stack>
          </Card>
        )}

        <Grid>
          <Card padding="lg">
            <SectionTitle>Words per commit</SectionTitle>
            <ChartBox>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={commitData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--bg-elevated)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="words" stroke="#32cd32" fill="rgba(50,205,50,0.15)" />
                </AreaChart>
              </ResponsiveContainer>
            </ChartBox>
          </Card>

          <Card padding="lg">
            <SectionTitle>Character presence</SectionTitle>
            <ChartBox>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={characterPresence} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--bg-elevated)" />
                  <XAxis type="number" tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} />
                  <YAxis
                    type="category"
                    dataKey="character"
                    width={80}
                    tick={{ fontSize: 11, fill: 'var(--text-secondary)' }}
                  />
                  <Tooltip />
                  <Bar dataKey="scenes" fill="#4a90d9" />
                </BarChart>
              </ResponsiveContainer>
            </ChartBox>
          </Card>

          <Card padding="lg">
            <SectionTitle>Dialogue vs action per scene</SectionTitle>
            <ChartBox>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={scenes.map((s) => ({ scene: `#${s.scene_number}`, dialogue: s.dialogue_words, action: s.action_words }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--bg-elevated)" />
                  <XAxis dataKey="scene" tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="dialogue" stackId="a" fill="#32cd32" />
                  <Bar dataKey="action" stackId="a" fill="#4a90d9" />
                </BarChart>
              </ResponsiveContainer>
            </ChartBox>
          </Card>

          <Card padding="lg">
            <SectionTitle>Scene mix</SectionTitle>
            <StatRow>
              <ChartBox>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={intExt} dataKey="value" nameKey="name" innerRadius={40} outerRadius={80}>
                      {intExt.map((_, i) => (
                        <Cell key={i} fill={ChartColors[i % ChartColors.length]} />
                      ))}
                    </Pie>
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </ChartBox>
              <ChartBox>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={dayNight} dataKey="value" nameKey="name" innerRadius={40} outerRadius={80}>
                      {dayNight.map((_, i) => (
                        <Cell key={i} fill={ChartColors[(i + 2) % ChartColors.length]} />
                      ))}
                    </Pie>
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </ChartBox>
            </StatRow>
          </Card>

          <Card padding="lg">
            <SectionTitle>Agent runs</SectionTitle>
            {(data?.agent_runs.length ?? 0) === 0 ? (
              <HelperText>No agent runs yet. Ask the coach something in the Agent Room.</HelperText>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Agent</th>
                    <th>Status</th>
                    <th>Elapsed</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.agent_runs.map((r) => (
                    <tr key={r.run_id}>
                      <td>{timeShort(r.created_at)}</td>
                      <td>{r.agent}</td>
                      <td>
                        <Chip color={r.status === 'completed' ? 'success' : r.status === 'error' ? 'danger' : 'warn'}>
                          {r.status}
                        </Chip>
                      </td>
                      <td>{r.elapsed_s.toFixed(1)}s</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>

          <Card padding="lg">
            <SectionTitle>Coverage history</SectionTitle>
            {(data?.coverage_history.length ?? 0) === 0 ? (
              <HelperText>No coverage yet. Run coverage from the Coverage page.</HelperText>
            ) : (
              <Stack gap={8}>
                {data?.coverage_history.map((c, i) => (
                  <StatRow key={i}>
                    <Chip
                      color={c.verdict === 'PASS' ? 'success' : c.verdict === 'RECOMMEND' ? 'accent' : 'warn'}
                    >
                      {c.verdict}
                    </Chip>
                    <span>{c.logline || '(no logline)'}</span>
                    <span>{timeShort(c.created_at)}</span>
                  </StatRow>
                ))}
              </Stack>
            )}
          </Card>
        </Grid>

        {scenes.length > 0 && (
          <Card padding="lg">
            <SectionTitle>Scene breakdown</SectionTitle>
            <Table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Heading</th>
                  <th>Cast</th>
                  <th>Words</th>
                </tr>
              </thead>
              <tbody>
                {scenes.map((s) => (
                  <tr key={s.scene_number}>
                    <td>{s.scene_number}</td>
                    <td>{s.heading}</td>
                    <td>{s.characters.join(', ') || '—'}</td>
                    <td>{s.dialogue_words + s.action_words}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        )}
      </Stack>
    </PageContainer>
  );
}
