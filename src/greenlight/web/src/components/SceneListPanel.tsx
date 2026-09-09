import styled from '@emotion/styled';
import { Card } from '../components';
import type { Scene } from '../lib/types';

const HeaderRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  min-height: 22px;
  gap: 8px;
`;

const ModeToggle = styled.div`
  display: inline-flex;
  background: var(--bg-elevated);
  border-radius: var(--radius);
  padding: 2px;
  gap: 2px;
  min-width: 0;
`;

const ModeButton = styled.button<{ active?: boolean }>`
  padding: 4px 10px;
  background: ${({ active }) => (active ? 'var(--accent)' : 'transparent')};
  color: ${({ active }) => (active ? 'var(--bg-base)' : 'var(--text-secondary)')};
  border: none;
  border-radius: calc(var(--radius) - 3px);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition);

  &:hover {
    color: ${({ active }) => (active ? 'var(--bg-base)' : 'var(--text-primary)')};
  }
`;

const ToggleButton = styled.button`
  background: none;
  border: 1px solid var(--bg-elevated);
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  line-height: 1;
  flex-shrink: 0;

  &:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }
`;

const PanelCard = styled(Card)`
  max-height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
`;

const SceneListScroll = styled.div`
  overflow-y: auto;
  min-height: 0;
  flex: 1;
`;

const SceneList_ = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const SceneItem = styled.button<{ active?: boolean }>`
  text-align: left;
  padding: 10px 12px;
  background: ${({ active }) => (active ? 'rgba(50, 205, 50, 0.12)' : 'var(--bg-surface)')};
  border: 1px solid ${({ active }) => (active ? 'var(--accent)' : 'var(--bg-elevated)')};
  border-radius: var(--radius);
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-primary);
  transition: all var(--transition);

  &:hover {
    border-color: var(--accent);
  }
`;

const SceneNum = styled.span`
  color: var(--accent);
  font-weight: 700;
  margin-right: 8px;
`;

const CollapsedRail = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
`;

const CollapsedItem = styled.button<{ active?: boolean }>`
  width: 32px;
  height: 32px;
  border-radius: 4px;
  background: ${({ active }) => (active ? 'rgba(50, 205, 50, 0.18)' : 'var(--bg-elevated)')};
  border: 1px solid ${({ active }) => (active ? 'var(--accent)' : 'var(--bg-elevated)')};
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;

  &:hover {
    border-color: var(--accent);
  }
`;

interface SceneListPanelProps {
  scenes: Scene[];
  activeIndex: number;
  onSelect: (index: number) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  mode: 'scenes' | 'all';
  onModeChange: (mode: 'scenes' | 'all') => void;
}

export function SceneListPanel({
  scenes,
  activeIndex,
  onSelect,
  collapsed,
  onToggleCollapse,
  mode,
  onModeChange,
}: SceneListPanelProps) {
  return (
    <PanelCard padding="md" className="scene-list-panel">
      <HeaderRow className="scene-list-header">
        {!collapsed && (
          <ModeToggle className="scene-list-mode-toggle">
            <ModeButton
              active={mode === 'scenes'}
              onClick={() => onModeChange('scenes')}
              className={`scene-list-mode-btn${mode === 'scenes' ? ' scene-list-mode-btn--active' : ''}`}
            >
              Scenes ({scenes.length})
            </ModeButton>
            <ModeButton
              active={mode === 'all'}
              onClick={() => onModeChange('all')}
              className={`scene-list-mode-btn${mode === 'all' ? ' scene-list-mode-btn--active' : ''}`}
            >
              Full Script
            </ModeButton>
          </ModeToggle>
        )}
        {collapsed && <span />}
        <ToggleButton
          onClick={onToggleCollapse}
          title={collapsed ? 'Expand scenes' : 'Collapse scenes'}
          aria-label={collapsed ? 'Expand scenes' : 'Collapse scenes'}
          className="scene-list-toggle"
        >
          {collapsed ? '›' : '‹'}
        </ToggleButton>
      </HeaderRow>

      {collapsed ? (
        <SceneListScroll className="scene-list-scroll">
          <CollapsedRail className="scene-list-collapsed-rail">
            {scenes.map((sc, i) => (
              <CollapsedItem
                key={sc.num}
                active={i === activeIndex}
                onClick={() => onSelect(i)}
                title={sc.heading}
                className={`scene-list-collapsed-item${i === activeIndex ? ' scene-list-collapsed-item--active' : ''}`}
              >
                {String(sc.num).padStart(2, '0').slice(-2)}
              </CollapsedItem>
            ))}
          </CollapsedRail>
        </SceneListScroll>
      ) : (
        <SceneListScroll className="scene-list-scroll">
          <SceneList_ className="scene-list">
            {scenes.map((sc, i) => (
              <SceneItem
                key={sc.num}
                active={i === activeIndex}
                onClick={() => onSelect(i)}
                className={`scene-list-item${i === activeIndex ? ' scene-list-item--active' : ''}`}
              >
                <SceneNum className="scene-list-item-num">{String(sc.num).padStart(2, '0')}</SceneNum>
                {sc.heading}
              </SceneItem>
            ))}
          </SceneList_>
        </SceneListScroll>
      )}
    </PanelCard>
  );
}