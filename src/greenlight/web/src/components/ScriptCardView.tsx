import styled from '@emotion/styled';
import type { Script } from '../lib/types';

const Card_ = styled.div`
  padding: 16px;
  background: var(--bg-surface);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 160px;
  cursor: pointer;
  transition: all var(--transition);

  &:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
  }
`;

const Title_ = styled.div`
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 8px;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const Meta = styled.div`
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
`;

const IconRow = styled.div`
  display: flex;
  gap: 6px;
  margin-top: 12px;
`;

const IconWrapper = styled.span`
  position: relative;
  display: inline-flex;

  &:hover > span {
    opacity: 1;
  }
`;

const IconButton = styled.button`
  padding: 6px 8px;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: none;
  border-radius: var(--radius);
  font-size: 14px;
  cursor: pointer;
  transition: all var(--transition);

  &:hover {
    background: var(--accent);
    color: var(--bg-base);
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
`;

const Tooltip = styled.span`
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 8px;
  background: var(--bg-base);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--transition);
  z-index: 10;
`;

interface ScriptCardProps {
  script: Script;
  onLoad: () => void;
  onCoverage: (e: React.MouseEvent) => void;
  onDelete: (e: React.MouseEvent) => void;
  coverageRunning: boolean;
}

export function ScriptCardView({ script, onLoad, onCoverage, onDelete, coverageRunning }: ScriptCardProps) {
  return (
    <Card_ className="script-card" onClick={onLoad}>
      <div className="script-card-body">
        <Title_ className="script-card-title">{script.title}</Title_>
        <Meta className="script-card-meta">{script.author || 'Unknown author'}</Meta>
        <Meta className="script-card-meta">
          Draft {script.draft} · {new Date(script.created_at).toLocaleDateString()}
        </Meta>
        {script.genre && <Meta className="script-card-meta">{script.genre}</Meta>}
      </div>
      <IconRow className="script-card-actions">
        <IconWrapper className="script-card-action">
          <Tooltip className="script-card-tooltip">Run Coverage</Tooltip>
          <IconButton className="script-card-action-btn" disabled={coverageRunning} onClick={onCoverage} title="Run Coverage">
            {coverageRunning ? '⏳' : '📄'}
          </IconButton>
        </IconWrapper>
        <IconWrapper className="script-card-action">
          <Tooltip className="script-card-tooltip">Delete</Tooltip>
          <IconButton className="script-card-action-btn" onClick={onDelete} title="Delete">🗑</IconButton>
        </IconWrapper>
      </IconRow>
    </Card_>
  );
}
