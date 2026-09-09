import { useCallback, useEffect, useState } from 'react';
import styled from '@emotion/styled';
import { Card, Chip } from '../index';
import { Button, ErrorText, HelperText, SectionTitle, Row, Stack } from '../layout.tsx';
import type { AgentRun } from '../../lib/types';
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

interface ShowrunnerPanelProps {
  scriptId: string;
}

export function ShowrunnerPanel({ scriptId }: ShowrunnerPanelProps) {
  const [prompt, setPrompt] = useState('');
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [result, setResult] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

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

  const loadRuns = useCallback(async () => {
    try {
      const res = await fetch(`/api/scripts/${scriptId}/agents/runs?agent=showrunner`);
      if (res.ok) setRuns(await res.json());
    } catch {
      // non-fatal
    }
  }, [scriptId]);

  useEffect(() => {
    setResult(null);
    void loadRuns();
  }, [loadRuns]);

  const handleRun = async () => {
    if (!prompt.trim()) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`/api/scripts/${scriptId}/showrunner`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt.trim() }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResult(data.response || data.result || '(no output)');
      await loadRuns();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Card padding="lg">
      <SectionTitle>Showrunner</SectionTitle>
      <HelperText>
        Routes your request to the right specialist — bible, analytics, or rewrite — and passes
        the script through so its tools target the correct data.
      </HelperText>

      <Stack gap={8}>
        <Row gap={8}>
          <Input
            placeholder="e.g. Check continuity, run the analytics, or rewrite the dialogue"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="showrunner-prompt-input"
          />
          <Button variant="primary" onClick={handleRun} disabled={running || !prompt.trim()}>
            {running ? 'Routing…' : 'Send to showrunner'}
          </Button>
        </Row>
      </Stack>

      {error && <ErrorText>{error}</ErrorText>}

      {result && <MarkdownBox header="Showrunner result:">{result}</MarkdownBox>}

      {runs.length > 0 && (
        <>
          <SectionTitle style={{ marginTop: 20 }}>Recent showrunner runs</SectionTitle>
          {runs.slice(0, 10).map((r) => {
            const open = expanded.has(r.run_id);
            const body = agentRunResponse(r);
            return (
              <RunRow key={r.run_id} className="showrunner-run">
                <RunHeader className="showrunner-run-header" onClick={() => toggle(r.run_id)}>
                  <Caret className="showrunner-run-caret">{open ? '▾' : '▸'}</Caret>
                  <Chip color={r.status === 'error' ? 'danger' : 'success'}>{r.status}</Chip>
                  <span>{r.created_at}</span>
                  <span>{r.elapsed_s}s</span>
                  {r.prompt && (
                    <span
                      className="showrunner-run-prompt"
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
    </Card>
  );
}
