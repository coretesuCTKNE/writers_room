import { useCallback, useEffect, useState } from 'react';
import styled from '@emotion/styled';
import { Card, Chip } from '../index';
import { Button, ErrorText, HelperText, SectionTitle, Row, Stack } from '../layout.tsx';
import type { AgentRun, CoverageData } from '../../lib/types';
import { MarkdownBox } from './MarkdownBox';

const Input = styled.input`
  padding: 8px 10px;
  background: var(--bg-base);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  &:focus {
    outline: none;
    border-color: var(--accent);
  }
`;

const MetaRow = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--text-secondary);
  font-size: 13px;
`;

interface RewritePanelProps {
  scriptId: string;
}

export function RewritePanel({ scriptId }: RewritePanelProps) {
  const [coverage, setCoverage] = useState<CoverageData | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [focus, setFocus] = useState('');
  const [instructions, setInstructions] = useState('');
  const [result, setResult] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadContext = useCallback(async () => {
    try {
      const [covRes, runsRes] = await Promise.all([
        fetch(`/api/scripts/${scriptId}/coverage/latest`),
        fetch(`/api/scripts/${scriptId}/agents/runs?agent=rewrite`),
      ]);
      if (covRes.ok) setCoverage(await covRes.json());
      if (runsRes.ok) setRuns(await runsRes.json());
    } catch {
      // non-fatal
    }
  }, [scriptId]);

  useEffect(() => {
    setCoverage(null);
    setResult(null);
    void loadContext();
  }, [loadContext]);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const textRes = await fetch(`/api/scripts/${scriptId}/text`);
      const scriptText = textRes.ok ? await textRes.text() : '';
      const res = await fetch(`/api/scripts/${scriptId}/rewrite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script_text: scriptText.slice(0, 120_000),
          focus,
          instructions,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResult(data.rewrite || '(no output)');
      await loadContext();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Card padding="lg">
      <SectionTitle>Rewrite specialist</SectionTitle>
      <HelperText>
        Produces targeted rewrite passes that address coverage notes while preserving story beats.
      </HelperText>

      {coverage && (
        <MetaRow className="rewrite-panel-coverage-note">
          <Chip variant="verdict">{coverage.verdict || 'CONSIDER'}</Chip>
          <span>latest coverage</span>
        </MetaRow>
      )}
      {!coverage && !error && (
        <HelperText>No coverage yet — the rewrite agent will work from the text alone.</HelperText>
      )}

      <Stack gap={8}>
        <Row gap={8}>
          <Input
            placeholder="Focus (e.g. dialogue, pacing, character)"
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            style={{ flex: 1 }}
            className="rewrite-panel-focus-input"
          />
          <Input
            placeholder="Additional instructions"
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            style={{ flex: 1 }}
            className="rewrite-panel-instructions-input"
          />
        </Row>
        <Row gap={8}>
          <Button variant="primary" onClick={handleRun} disabled={running}>
            {running ? 'Rewriting…' : 'Run rewrite pass'}
          </Button>
        </Row>
      </Stack>

      {error && <ErrorText>{error}</ErrorText>}

      {result && <MarkdownBox header="Rewrite result:">{result}</MarkdownBox>}

      {runs.length > 0 && (
        <>
          <SectionTitle style={{ marginTop: 20 }}>Recent rewrite passes</SectionTitle>
          {runs.slice(0, 5).map((r) => (
            <MetaRow key={r.run_id} className="rewrite-panel-run">
              <Chip color={r.status === 'error' ? 'danger' : 'success'}>{r.status}</Chip>
              <span>{r.created_at}</span>
              <span>{r.elapsed_s}s</span>
            </MetaRow>
          ))}
        </>
      )}
    </Card>
  );
}
