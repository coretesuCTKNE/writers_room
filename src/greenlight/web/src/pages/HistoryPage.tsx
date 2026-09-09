import { useEffect, useState } from 'react';
import styled from '@emotion/styled';
import { AudioLibrary, Card, Chip } from '../components';
import { HelperText, PageContainer, PageTitle } from '../components/layout.tsx';
import type { EditEntry } from '../lib/types';

const Timeline = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const EditItem = styled.div`
  padding: 16px;
  background: var(--bg-surface);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all var(--transition);

  &:hover {
    border-color: var(--accent);
  }
`;

const EditHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
`;

const EditMeta = styled.div`
  font-size: 12px;
  color: var(--text-secondary);
`;

const DiffPreview = styled.div`
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 8px;
  background: var(--bg-elevated);
  border-radius: 4px;
  margin-top: 8px;
  max-height: 80px;
  overflow: hidden;
`;

const SceneLabel = styled.div`
  font-size: 13px;
`;

export function HistoryPage() {
  const [edits, setEdits] = useState<EditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/history/edits')
      .then((r) => r.json())
      .then((data) => {
        setEdits(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <PageContainer className="history-page">
      <PageTitle className="history-page-title">Edit History</PageTitle>

      <AudioLibrary />

      {loading ? (
        <Card padding="lg" className="history-loading-card">
          <HelperText>Loading...</HelperText>
        </Card>
      ) : edits.length === 0 ? (
        <Card padding="lg" className="history-empty-card">
          <HelperText>
            No edits yet. Run coverage or rewrite a script to generate edits.
          </HelperText>
        </Card>
      ) : (
        <Timeline className="history-timeline">
          {edits.map((edit) => (
            <EditItem key={edit.edit_id} className="history-edit-item">
              <EditHeader className="history-edit-header">
                <Chip variant="status">{edit.source}</Chip>
                <EditMeta className="history-edit-meta">{edit.created_at}</EditMeta>
              </EditHeader>
              <SceneLabel className="history-scene-label">
                Scene: <strong>{edit.scene_id}</strong>
              </SceneLabel>
              <DiffPreview className="history-diff-preview">{edit.after_md.slice(0, 200)}...</DiffPreview>
            </EditItem>
          ))}
        </Timeline>
      )}
    </PageContainer>
  );
}
