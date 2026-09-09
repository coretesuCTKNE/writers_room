import styled from '@emotion/styled';
import { useState } from 'react';
import { Card } from '../components';
import { Button, Row } from '../components/layout.tsx';
import type { VersionMeta } from '../lib/types';

const SectionHeading = styled.div`
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-secondary);
  margin-bottom: 10px;
`;

const Select = styled.select`
  padding: 8px 10px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  font-size: 13px;
`;

const DiffBox = styled.pre`
  max-height: 260px;
  overflow-y: auto;
  padding: 12px;
  background: var(--bg-base);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  margin: 0;
`;

const DiffAdd = styled.span`
  color: var(--success);
`;

const DiffDel = styled.span`
  color: var(--danger);
`;

interface DiffChange {
  ordinal: number;
  change: string;
  before?: string;
  after?: string;
}

interface DiffPanelProps {
  versions: VersionMeta[];
  activeVersionId: string;
}

export function DiffPanel({ versions, activeVersionId }: DiffPanelProps) {
  const [compareBase, setCompareBase] = useState<string>('');
  const [diffChanges, setDiffChanges] = useState<DiffChange[] | null>(null);

  const showDiff = async () => {
    if (!compareBase) return;
    const res = await fetch(`/api/versions/${compareBase}/diff/${activeVersionId}`);
    if (!res.ok) return;
    const data = await res.json();
    setDiffChanges(data.changes);
  };

  const others = versions.filter((v) => v.version_id !== activeVersionId);

  return (
    <Card padding="lg" className="diff-panel">
      <SectionHeading className="diff-panel-title">Compare</SectionHeading>
      <Row className="diff-panel-controls" style={{ marginTop: 0 }}>
        <Select className="diff-panel-select" value={compareBase} onChange={(e) => setCompareBase(e.target.value)}>
          <option value="">Compare… vs current head</option>
          {others.map((v) => (
            <option key={v.version_id} value={v.version_id}>
              {v.version_id.slice(0, 8)} {v.message}
            </option>
          ))}
        </Select>
        <Button variant="ghost" onClick={showDiff} disabled={!compareBase}>
          Show Diff
        </Button>
      </Row>
      {diffChanges && (
        <DiffBox className="diff-panel-box">
          {diffChanges.length === 0
            ? 'No differences.'
            : diffChanges.map((c, i) => (
                <div key={i}>
                  {c.change === 'added' && (
                    <DiffAdd className="diff-panel-add">+ [{c.ordinal}] {(c.after ?? '').slice(0, 120)}</DiffAdd>
                  )}
                  {c.change === 'removed' && (
                    <DiffDel className="diff-panel-del">- [{c.ordinal}] {(c.before ?? '').slice(0, 120)}</DiffDel>
                  )}
                  {c.change === 'modified' && (
                    <>
                      <DiffDel className="diff-panel-del">- {(c.before ?? '').slice(0, 120)}</DiffDel>
                      {'\n'}
                      <DiffAdd className="diff-panel-add">+ {(c.after ?? '').slice(0, 120)}</DiffAdd>
                    </>
                  )}
                </div>
              ))}
        </DiffBox>
      )}
    </Card>
  );
}
