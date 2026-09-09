import { useCallback, useEffect, useState } from 'react';
import styled from '@emotion/styled';
import { Card, Chip } from '../index';
import { Button, ErrorText, HelperText, SectionTitle, Row, Stack } from '../layout.tsx';
import type { AgentRun, BibleFact } from '../../lib/types';
import { MarkdownBox, agentRunResponse } from './MarkdownBox';

const BIBLE_CATEGORIES = [
  'personality',
  'relationship',
  'backstory',
  'world_rule',
  'timeline',
  'physical_trait',
  'motivation',
  'secret',
];

const FactsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  margin-top: 12px;
`;

const FactCard = styled.div`
  padding: 12px;
  background: var(--bg-elevated);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const FactText = styled.div`
  font-size: 13px;
  line-height: 1.5;
`;

const FactMeta = styled.div`
  font-size: 11px;
  color: var(--text-secondary);
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
`;

const DelBtn = styled.button`
  margin-left: auto;
  background: none;
  border: none;
  color: var(--danger);
  cursor: pointer;
  font-size: 12px;
  &:hover {
    opacity: 0.8;
  }
`;

const FormRow = styled(Row)``;

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

const Select = styled.select`
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

interface BiblePanelProps {
  scriptId: string;
}

export function BiblePanel({ scriptId }: BiblePanelProps) {
  const [facts, setFacts] = useState<BibleFact[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningCheck, setRunningCheck] = useState(false);
  const [checkResult, setCheckResult] = useState<string | null>(null);

  const [character, setCharacter] = useState('');
  const [category, setCategory] = useState(BIBLE_CATEGORIES[0]);
  const [claim, setClaim] = useState('');
  const [page, setPage] = useState('1');
  const [adding, setAdding] = useState(false);

  const loadFacts = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(`/api/scripts/${scriptId}/bible-facts`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setFacts(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [scriptId]);

  const loadRuns = useCallback(async () => {
    try {
      const res = await fetch(`/api/scripts/${scriptId}/agents/runs?agent=bible`);
      if (res.ok) setRuns(await res.json());
    } catch {
      // non-fatal
    }
  }, [scriptId]);

  const loadLastCheck = useCallback(async () => {
    try {
      const res = await fetch(`/api/scripts/${scriptId}/agents/runs?agent=bible&limit=1`);
      if (!res.ok) return;
      const latest: AgentRun[] = await res.json();
      const done = latest.find((r) => r.status === 'completed');
      if (done) {
        const body = agentRunResponse(done);
        if (body) setCheckResult(body);
      }
    } catch {
      // non-fatal
    }
  }, [scriptId]);

  useEffect(() => {
    setLoading(true);
    setFacts([]);
    setCheckResult(null);
    void loadFacts();
    void loadRuns();
    void loadLastCheck();
  }, [loadFacts, loadRuns, loadLastCheck]);

  const handleAdd = async () => {
    if (!character.trim() || !claim.trim()) return;
    setAdding(true);
    setError(null);
    try {
      const res = await fetch(`/api/scripts/${scriptId}/bible-facts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character_id: character.trim(),
          category,
          claim: claim.trim(),
          source_page: Number(page) || 0,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setCharacter('');
      setClaim('');
      setPage('1');
      await loadFacts();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (factId: string) => {
    try {
      await fetch(`/api/scripts/${scriptId}/bible-facts/${factId}`, { method: 'DELETE' });
      await new Promise((r) => setTimeout(r, 1200));
      await loadFacts();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleCheck = async () => {
    setRunningCheck(true);
    setError(null);
    setCheckResult(null);
    try {
      const textRes = await fetch(`/api/scripts/${scriptId}/text`);
      const scriptText = textRes.ok ? await textRes.text() : '';
      const res = await fetch(`/api/scripts/${scriptId}/bible-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script_text: scriptText.slice(0, 120_000) }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCheckResult(data.bible_check || '(no result)');
      await Promise.all([loadFacts(), loadRuns()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunningCheck(false);
    }
  };

  const grouped = facts.reduce<Record<string, BibleFact[]>>((acc, f) => {
    (acc[f.character_id] = acc[f.character_id] || []).push(f);
    return acc;
  }, {});

  return (
    <Card padding="lg">
      <SectionTitle>Story Bible — continuity facts</SectionTitle>
      <HelperText>
        The bible agent verifies the screenplay against these facts and extracts new ones. Facts
        are stored per-character.
      </HelperText>

      <Row gap={8}>
        <Button variant="primary" onClick={handleCheck} disabled={runningCheck}>
          {runningCheck ? 'Checking…' : 'Run continuity check'}
        </Button>
        <Button onClick={loadLastCheck}>Reload last check</Button>
        <Chip color="neutral">{facts.length} facts</Chip>
      </Row>

      {error && <ErrorText>{error}</ErrorText>}

      {checkResult && <MarkdownBox header="Bible check result:">{checkResult}</MarkdownBox>}

      <SectionTitle style={{ marginTop: 20 }}>Add fact</SectionTitle>
      <Stack gap={8}>
        <FormRow gap={8}>
          <Input
            placeholder="Character (e.g. DETECTIVE)"
            value={character}
            onChange={(e) => setCharacter(e.target.value)}
            className="bible-panel-character-input"
          />
          <Select value={category} onChange={(e) => setCategory(e.target.value)} className="bible-panel-category-select">
            {BIBLE_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <Input
            placeholder="Page"
            value={page}
            onChange={(e) => setPage(e.target.value)}
            style={{ width: 60 }}
            className="bible-panel-page-input"
          />
        </FormRow>
        <Row gap={8}>
          <Input
            placeholder="Claim (e.g. Stoic under pressure)"
            value={claim}
            onChange={(e) => setClaim(e.target.value)}
            style={{ flex: 1 }}
            className="bible-panel-claim-input"
          />
          <Button onClick={handleAdd} disabled={adding || !character || !claim}>
            {adding ? 'Adding…' : 'Add fact'}
          </Button>
        </Row>
      </Stack>

      {Object.keys(grouped).length === 0 && !loading ? (
        <HelperText style={{ marginTop: 12 }}>
          No facts yet. Run a continuity check or add facts manually above.
        </HelperText>
      ) : (
        Object.entries(grouped).map(([charId, charFacts]) => (
          <div key={charId} className="bible-panel-character-group">
            <SectionTitle style={{ marginTop: 20 }}>
              {charId || '(unspecified)'}
            </SectionTitle>
            <FactsGrid className="bible-panel-facts-grid">
              {charFacts.map((f) => (
                <FactCard key={f.fact_id} className="bible-panel-fact">
                  <FactText className="bible-panel-fact-text">{f.claim}</FactText>
                  <FactMeta className="bible-panel-fact-meta">
                    <Chip color="accent">{f.category}</Chip>
                    {f.source_page > 0 && <span>p.{f.source_page}</span>}
                    <DelBtn className="bible-panel-fact-delete" onClick={() => handleDelete(f.fact_id)}>delete</DelBtn>
                  </FactMeta>
                </FactCard>
              ))}
            </FactsGrid>
          </div>
        ))
      )}

      {runs.length > 0 && (
        <>
          <SectionTitle style={{ marginTop: 24 }}>Recent bible runs</SectionTitle>
          {runs.slice(0, 5).map((r) => (
            <FactMeta key={r.run_id} className="bible-panel-run">
              <Chip color={r.status === 'error' ? 'danger' : 'success'}>{r.status}</Chip>
              <span>{r.created_at}</span>
              <span>{r.elapsed_s}s</span>
            </FactMeta>
          ))}
        </>
      )}
    </Card>
  );
}
