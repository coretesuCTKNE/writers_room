import styled from '@emotion/styled';
import { useCallback, useEffect, useState } from 'react';
import { Button, ErrorText, HelperText, Stack } from './layout.tsx';
import type { GoalMetric, WritingGoal } from '../lib/types';

const PanelHeading = styled.div`
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-secondary);
  margin-bottom: 10px;
`;

const GoalRow = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 0;
  border-bottom: 1px solid var(--bg-elevated);

  &:last-child {
    border-bottom: none;
  }
`;

const GoalTop = styled.div`
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
`;

const GoalLabel = styled.span`
  font-weight: 600;
  color: var(--text-primary);
`;

const GoalNumbers = styled.span`
  color: var(--text-secondary);
`;

const RemoveButton = styled.button`
  margin-left: auto;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;

  &:hover {
    color: var(--danger);
  }
`;

const ProgressBar = styled.div`
  height: 6px;
  border-radius: 3px;
  background: var(--bg-elevated);
  overflow: hidden;
`;

const ProgressFill = styled.div<{ pct: number; done: boolean }>`
  height: 100%;
  width: ${({ pct }) => pct}%;
  background: ${({ done }) => (done ? 'var(--success, #3fb96f)' : 'var(--accent)')};
  transition: width 0.3s ease;
`;

const AddForm = styled.div`
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
  align-items: center;
`;

const MetricSelect = styled.select`
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  padding: 6px 8px;
  font-size: 12px;
`;

const TargetInput = styled.input`
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  padding: 6px 8px;
  font-size: 12px;
  width: 90px;
`;

const DateInput = styled.input`
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  padding: 6px 8px;
  font-size: 12px;
`;

function formatCurrent(goal: WritingGoal): string {
  const value = goal.current.toLocaleString();
  const target = goal.target.toLocaleString();
  const unit = goal.metric === 'words' ? 'words' : goal.metric;
  if (goal.days_left !== null) {
    const pace =
      goal.remaining === 0
        ? 'done'
        : goal.days_left < 0
          ? `${-goal.days_left}d overdue`
          : `${goal.days_left}d left`;
    return `${value} / ${target} ${unit} · ${pace}`;
  }
  return `${value} / ${target} ${unit}`;
}

interface GoalsPanelProps {
  scriptId: string;
}

export function GoalsPanel({ scriptId }: GoalsPanelProps) {
  const [goals, setGoals] = useState<WritingGoal[]>([]);
  const [metric, setMetric] = useState<GoalMetric>('words');
  const [target, setTarget] = useState('');
  const [deadline, setDeadline] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/scripts/${scriptId}/goals`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setGoals(await res.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [scriptId]);

  useEffect(() => {
    void load();
  }, [load]);

  const addGoal = async () => {
    const targetNum = parseInt(target, 10);
    if (!targetNum || targetNum <= 0) {
      setError('Target must be a positive number');
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`/api/scripts/${scriptId}/goals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          metric,
          target: targetNum,
          deadline: deadline || null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setTarget('');
      setDeadline('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const removeGoal = async (goalId: string) => {
    try {
      const res = await fetch(`/api/scripts/${scriptId}/goals/${goalId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <Stack gap={8} className="goals-panel">
      <PanelHeading className="goals-panel-heading">Writing Goals</PanelHeading>
      {error && <ErrorText className="goals-panel-error">{error}</ErrorText>}
      {goals.length === 0 && !error && (
        <HelperText>
          No goals yet. Set a draft target — progress updates on every commit and feeds the
          Story Ops dashboard in Grafana.
        </HelperText>
      )}
      {goals.map((goal) => (
        <GoalRow key={goal.goal_id} className="goals-row">
          <GoalTop className="goals-row-top">
            <GoalLabel className="goals-row-label">{goal.note || `Draft ${goal.metric} goal`}</GoalLabel>
            <GoalNumbers className="goals-row-numbers">{formatCurrent(goal)}</GoalNumbers>
            <RemoveButton className="goals-row-remove" onClick={() => void removeGoal(goal.goal_id)}>✕</RemoveButton>
          </GoalTop>
          <ProgressBar className="goals-row-progress">
            <ProgressFill pct={goal.pct} done={goal.remaining === 0} className="goals-row-progress-fill" />
          </ProgressBar>
        </GoalRow>
      ))}
      <AddForm className="goals-add-form">
        <MetricSelect className="goals-add-metric" value={metric} onChange={(e) => setMetric(e.target.value as GoalMetric)}>
          <option value="words">words</option>
          <option value="pages">pages</option>
          <option value="scenes">scenes</option>
        </MetricSelect>
        <TargetInput
          type="number"
          min={1}
          placeholder="target"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          className="goals-add-target"
        />
        <DateInput
          type="date"
          value={deadline}
          onChange={(e) => setDeadline(e.target.value)}
          className="goals-add-deadline"
        />
        <Button variant="primary" disabled={busy} onClick={() => void addGoal()}>
          {busy ? 'Adding…' : 'Set goal'}
        </Button>
      </AddForm>
    </Stack>
  );
}
