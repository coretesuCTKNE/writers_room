import styled from '@emotion/styled';
import { useMemo } from 'react';
import { Card } from '../components';
import { Button } from '../components/layout.tsx';
import type { VersionMeta } from '../lib/types';

const SectionHeading = styled.div`
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-secondary);
  margin-bottom: 10px;
`;

const VersionList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
`;

const VersionRow = styled.div<{ active?: boolean }>`
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: ${({ active }) => (active ? 'rgba(50, 205, 50, 0.1)' : 'var(--bg-surface)')};
  border: 1px solid ${({ active }) => (active ? 'var(--accent)' : 'var(--bg-elevated)')};
  border-radius: var(--radius);
  font-size: 12px;
`;

const VersionLabel = styled.div<{ active?: boolean }>`
  min-width: 0;
  color: ${({ active }) => (active ? 'var(--accent)' : 'var(--text-primary)')};
`;

const Hash = styled.code`
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 11px;
`;

const VersionMetaText = styled.div`
  color: var(--text-secondary);
  font-size: 11px;
  margin-top: 2px;
`;

const Actions = styled.div`
  display: flex;
  gap: 4px;
`;

const CompactButton = styled(Button)`
  padding: 4px 8px;
  font-size: 11px;
`;

interface VersionHistoryProps {
  versions: VersionMeta[];
  branchId: string;
  activeVersionId: string;
  onPeek: (versionId: string) => void;
  onRevert: (versionId: string) => void;
}

export function VersionHistory({ versions, branchId, activeVersionId, onPeek, onRevert }: VersionHistoryProps) {
  const onBranch = useMemo(
    () => [...versions.filter((v) => v.branch_id === branchId)].reverse(),
    [versions, branchId],
  );
  return (
    <Card padding="md" className="version-history">
      <SectionHeading className="version-history-title">History ({onBranch.length} on branch)</SectionHeading>
      <VersionList className="version-history-list">
        {onBranch.map((v) => (
          <VersionRow key={v.version_id} active={v.version_id === activeVersionId} className={`version-history-version${v.version_id === activeVersionId ? ' version-history-version--active' : ''}`}>
            <VersionLabel active={v.version_id === activeVersionId} className="version-history-version-label">
              <Hash className="version-history-hash">{v.version_id.slice(0, 8)}</Hash> {v.message}
              <VersionMetaText className="version-history-version-meta">
                {v.author || '—'} · {new Date(v.created_at.replace(' ', 'T')).toLocaleString()}
              </VersionMetaText>
            </VersionLabel>
            <Actions className="version-history-actions">
              <CompactButton variant="ghost" onClick={() => onPeek(v.version_id)}>Peek</CompactButton>
              {v.version_id !== activeVersionId && (
                <CompactButton variant="danger" onClick={() => onRevert(v.version_id)}>Revert</CompactButton>
              )}
            </Actions>
          </VersionRow>
        ))}
      </VersionList>
    </Card>
  );
}
