import styled from '@emotion/styled';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProjectStore } from '../lib/store-project';
import type { SessionState } from '../lib/types';

const ScriptLoader = styled.div`
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ActiveScript = styled.div`
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const ActiveVersion = styled.div`
  font-size: 11px;
  color: var(--accent);
  white-space: nowrap;
`;

const LoaderRow = styled.div`
  display: flex;
  gap: 6px;
`;

const MiniButton = styled.button<{ block?: boolean; accent?: boolean }>`
  flex: ${({ block }) => (block ? 'none' : 1)};
  width: ${({ block }) => (block ? '100%' : 'auto')};
  padding: ${({ block }) => (block ? '5px 8px' : '3px 8px')};
  background: var(--bg-elevated);
  color: ${({ accent }) => (accent ? 'var(--accent)' : 'var(--text-secondary)')};
  border: none;
  border-radius: 4px;
  font-size: 11px;
  text-align: ${({ block }) => (block ? 'left' : 'center')};
  cursor: pointer;
  transition: all var(--transition);

  &:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }
`;

const PickerList = styled.div`
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 240px;
  padding: 8px;
  background: var(--bg-surface);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  z-index: 30;
`;

const PickerItem = styled(MiniButton)`
  display: block;
  margin-bottom: 4px;
`;

const PickerEmpty = styled.div`
  font-size: 11px;
  color: var(--text-secondary);
`;

const InactiveText = styled(ActiveScript)`
  color: var(--text-secondary);
  font-weight: 400;
`;

interface ScriptPickerProps {
  session: SessionState | null;
}

export function ScriptPicker({ session }: ScriptPickerProps) {
  const scripts = useProjectStore((s) => s.scripts);
  const loadScript = useProjectStore((s) => s.loadScript);
  const unloadScript = useProjectStore((s) => s.unloadScript);
  const [pickerOpen, setPickerOpen] = useState(false);
  const navigate = useNavigate();

  const activeBranch = session?.branches.find((b) => b.branch_id === session?.branchId);

  const onLoad = async (id: string) => {
    await loadScript(id);
    setPickerOpen(false);
  };

  return (
    <ScriptLoader className="script-picker">
      {session?.loaded ? (
        <>
          <ActiveScript title={session.title} className="script-picker-active-title">{session.title}</ActiveScript>
          <ActiveVersion className="script-picker-active-version">
            {activeBranch?.name ?? 'main'}@{(session.versionId || '?').slice(0, 8)}
          </ActiveVersion>
          <LoaderRow className="script-picker-loader-row">
            <MiniButton className="script-picker-btn" onClick={() => navigate('/screenplay')}>Edit</MiniButton>
            <MiniButton className="script-picker-btn" onClick={() => setPickerOpen(!pickerOpen)}>Switch</MiniButton>
            <MiniButton className="script-picker-btn" onClick={() => unloadScript()}>Unload</MiniButton>
          </LoaderRow>
        </>
      ) : (
        <>
          <InactiveText className="script-picker-inactive-text">No screenplay loaded</InactiveText>
          <LoaderRow className="script-picker-loader-row">
            <MiniButton className="script-picker-btn" onClick={() => setPickerOpen(!pickerOpen)}>Load…</MiniButton>
            <MiniButton className="script-picker-btn script-picker-btn--upload" onClick={() => navigate('/workspace')}>Upload</MiniButton>
          </LoaderRow>
        </>
      )}
      {pickerOpen && (
        <PickerList className="script-picker-list">
          {scripts.map((s) => (
            <PickerItem
              key={s.id}
              block
              accent={session?.scriptId === s.id}
              onClick={() => onLoad(s.id)}
              className={`script-picker-item${session?.scriptId === s.id ? ' script-picker-item--active' : ''}`}
            >
              {s.title}
            </PickerItem>
          ))}
          {scripts.length === 0 && (
            <PickerEmpty className="script-picker-empty">No scripts yet — upload one in Workspace</PickerEmpty>
          )}
        </PickerList>
      )}
    </ScriptLoader>
  );
}