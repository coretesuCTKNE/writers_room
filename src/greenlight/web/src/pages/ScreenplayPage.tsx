import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from '@emotion/styled';
import { Card } from '../components';
import { DictationOverlay } from '../components/DictationOverlay';
import { DiffPanel } from '../components/DiffPanel';
import { GoalsPanel } from '../components/GoalsPanel';
import { SceneEditor } from '../components/SceneEditor';
import { SceneListPanel } from '../components/SceneListPanel';
import { VersionHistory } from '../components/VersionHistory';
import { Button, PageTitle, FullHeightContainer, WidePageContainer } from '../components/layout.tsx';
import { useDictationStore } from '../lib/store-dictation';
import { useProjectStore } from '../lib/store-project';
import type { Scene, VersionMeta } from '../lib/types';

const Columns = styled.div<{ sidebarWidth?: string }>`
  display: grid;
  grid-template-columns: ${({ sidebarWidth = '280px' }) => `${sidebarWidth} 1fr`};
  grid-template-rows: 1fr;
  gap: 16px;
  align-items: stretch;
  min-height: 0;
`;

const EditorColumn = styled.div`
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
`;

const EditorCard = styled(Card)`
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
`;

const TabBar = styled.div`
  flex-shrink: 0;
`;

const TabRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 6px;
  margin-bottom: 8px;
`;

const TabButton = styled.button<{ active?: boolean }>`
  background: ${({ active }) => (active ? 'var(--accent)' : 'var(--bg-elevated)')};
  color: ${({ active }) => (active ? 'var(--bg-base)' : 'var(--text-secondary)')};
  border: 1px solid ${({ active }) => (active ? 'var(--accent)' : 'var(--bg-elevated)')};
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all var(--transition);

  &:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }
`;

const TabDirtyDot = styled.span`
  color: var(--accent);
`;

const TabCollapse = styled.button`
  background: none;
  border: 1px solid var(--bg-elevated);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: var(--radius);

  &:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }
`;

const TabBody = styled.div<{ open: boolean }>`
  overflow: hidden;
  max-height: ${({ open }) => (open ? '260px' : '0')};
  opacity: ${({ open }) => (open ? 1 : 0)};
  transition: max-height 0.25s ease, opacity 0.2s ease;
`;

const StatusLine = styled.div<{ error?: boolean }>`
  font-size: 13px;
  line-height: 1.4;
  color: ${({ error }) => (error ? 'var(--danger)' : 'var(--success)')};
`;

const CommitField = styled.div<{ $reviewing: boolean }>`
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  opacity: ${({ $reviewing }) => ($reviewing ? 0.55 : 1)};
  pointer-events: ${({ $reviewing }) => ($reviewing ? 'none' : 'auto')};
`;

const CommitInput = styled.input`
  flex: 1;
  min-width: 180px;
  padding: 8px 10px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  font-size: 13px;

  &:focus {
    outline: none;
    border-color: var(--accent);
  }
`;

const BranchInput = styled(CommitInput)`
  flex: 0 1 220px;
  min-width: 160px;
`;

const TabCard = styled(Card)`
  display: flex;
  min-height: 0;
`;

const TitleSuffix = styled.span`
  font-size: 13px;
  font-weight: 400;
  color: var(--accent);
  margin-left: 12px;
`;

const EmptyMessage = styled.p`
  color: var(--text-secondary);
  margin: 0;
`;

const InlineLink = styled.button`
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  text-decoration: underline;
`;

export function ScreenplayPage() {
  const session = useProjectStore((s) => s.session);
  const refreshSession = useProjectStore((s) => s.refreshSession);
  const setActiveVersion = useProjectStore((s) => s.setActiveVersion);
  const markEditedScene = useProjectStore((s) => s.markEditedScene);
  const navigate = useNavigate();

  const dictationActive = useDictationStore((s) => s.session?.active ?? false);
  const startDictation = useDictationStore((s) => s.startDictation);
  const stopDictation = useDictationStore((s) => s.stopDictation);
  const targetCharacter = useDictationStore((s) => s.targetCharacter);
  const setTargetCharacter = useDictationStore((s) => s.setTargetCharacter);
  const pushUndoEntry = useDictationStore((s) => s.pushUndoEntry);
  const popUndoEntry = useDictationStore((s) => s.popUndoEntry);

  const [versions, setVersions] = useState<VersionMeta[]>([]);
  const [sceneList, setSceneList] = useState<Scene[]>([]);
  const [sceneIdx, setSceneIdx] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [commitMsg, setCommitMsg] = useState('');
  const [branchName, setBranchName] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(
    () => localStorage.getItem('screenplay.scenesCollapsed') === 'true',
  );
  const [tabsOpen, setTabsOpen] = useState<boolean>(
    () => localStorage.getItem('screenplay.tabsOpen') === 'true',
  );
  const [activeTab, setActiveTab] = useState<'commit' | 'goals' | 'history'>(
    () => (localStorage.getItem('screenplay.activeTab') as 'commit' | 'goals' | 'history') ?? 'commit',
  );
  const [docMode, setDocModeState] = useState<'scenes' | 'all'>(
    () => (localStorage.getItem('screenplay.docMode') as 'scenes' | 'all') ?? 'scenes',
  );

  const setDocMode = (mode: 'scenes' | 'all') => {
    if (mode !== docMode && dirty && !confirm('Discard unsaved changes?')) return;
    setDocModeState(mode);
  };

  useEffect(() => {
    localStorage.setItem('screenplay.docMode', docMode);
  }, [docMode]);

  useEffect(() => {
    localStorage.setItem('screenplay.scenesCollapsed', String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => {
    localStorage.setItem('screenplay.tabsOpen', String(tabsOpen));
  }, [tabsOpen]);

  useEffect(() => {
    localStorage.setItem('screenplay.activeTab', activeTab);
  }, [activeTab]);

  const scriptId = session?.scriptId ?? '';
  const branchId = session?.branchId ?? '';
  const versionId = session?.versionId ?? '';

  // Keep the editor on the same scene number across version reloads (commits/reverts)
  const selectedSceneNumRef = useRef<number | null>(null);

  const loadVersion = useCallback(async (vid: string) => {
    const res = await fetch(`/api/versions/${vid}`);
    if (!res.ok) return;
    const data = await res.json();
    const scenes: Scene[] = data.scenes ?? [];
    setSceneList(scenes);
    setDirty(false);
    if (scenes.length === 0) {
      // No scene headings: the scene editor would render blank even though
      // content is saved. Fall back to the full-document view so the writer
      // sees their text (bypasses the unsaved-changes confirm — there is no
      // scene content to discard when the scene list is empty).
      const txtRes = await fetch(`/api/versions/${vid}/fountain`);
      if (txtRes.ok) {
        setFullDraft(await txtRes.text());
        setDocModeState('all');
      }
    }
    const keep = selectedSceneNumRef.current;
    if (keep !== null) {
      const idx = scenes.findIndex((s) => s.num === keep);
      setSceneIdx(idx >= 0 ? idx : 0);
      if (idx < 0) selectedSceneNumRef.current = null;
    } else {
      setSceneIdx(0);
    }
  }, []);

  const selectScene = useCallback(
    (idx: number) => {
      setSceneIdx(idx);
      const sc = sceneList[idx];
      selectedSceneNumRef.current = sc ? sc.num : null;
    },
    [sceneList],
  );

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    if (!scriptId) return;
    fetch(`/api/scripts/${scriptId}/repo`)
      .then((r) => r.json())
      .then((data) => setVersions(data.versions ?? []))
      .catch(() => {});
  }, [scriptId]);

  useEffect(() => {
    if (versionId) loadVersion(versionId);
  }, [versionId, loadVersion]);

  const currentScene = sceneList[Math.min(sceneIdx, Math.max(sceneList.length - 1, 0))];
  const [sceneDraft, setSceneDraft] = useState('');
  const [fullDraft, setFullDraft] = useState('');

  // Load the whole-document fountain text when Full Script mode is active.
  useEffect(() => {
    if (docMode !== 'all' || !versionId) return;
    fetch(`/api/versions/${versionId}/fountain`)
      .then((r) => r.text())
      .then((t) => {
        setFullDraft(t);
        setDirty(false);
      })
      .catch(() => {});
  }, [docMode, versionId]);

  // Synchronous mirror of sceneDraft for undo snapshots + delete slicing
  const draftRef = useRef(sceneDraft);
  draftRef.current = sceneDraft;

  useEffect(() => {
    setSceneDraft(currentScene ? currentScene.text : '');
  }, [currentScene?.num]);

  const refreshRepo = async () => {
    const repoRes = await fetch(`/api/scripts/${scriptId}/repo`);
    setVersions((await repoRes.json()).versions ?? []);
  };

  const commitScene = async () => {
    if (!scriptId || !versionId) return;
    if (!sceneDraft.trim()) {
      if (sceneList.length === 0) {
        setStatus(
          'No scene headings yet — write in Full Script mode or add a scene heading (e.g. INT. CAFE - DAY).',
        );
      }
      return;
    }
    await commitVersion({
      branchId,
      versionId,
      message: commitMsg || `Edit scene ${currentScene?.num ?? 1}`,
      sceneNumber: currentScene?.num ?? 1,
      payload: { scene: { number: currentScene?.num ?? 1, text: sceneDraft } },
    });
  };

  const commitFull = async () => {
    if (!fullDraft.trim() || !scriptId || !versionId) return;
    await commitVersion({
      branchId,
      versionId,
      message: commitMsg || 'Edit full script',
      payload: { raw_fountain: fullDraft },
    });
  };

  // Shared commit path: optional new branch, then POST {base, message, ...payload}.
  // On success, bumps active version, refreshes repo, clears dirty state.
  const commitVersion = async (opts: {
    branchId: string;
    versionId: string;
    message: string;
    sceneNumber?: number;
    payload: Record<string, unknown>;
  }) => {
    setStatus('Committing…');
    try {
      let targetBranch = opts.branchId;

      if (branchName.trim()) {
        const res = await fetch(`/api/scripts/${scriptId}/branches`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: branchName.trim(), from_version_id: opts.versionId }),
        });
        if (!res.ok) throw new Error(await res.text());
        targetBranch = (await res.json()).branch_id;
      }

      if (opts.sceneNumber !== undefined) {
        selectedSceneNumRef.current = opts.sceneNumber;
      }
      const res = await fetch(`/api/scripts/${scriptId}/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          branch_id: targetBranch,
          base_version_id: opts.versionId,
          message: opts.message,
          author: 'writer',
          ...opts.payload,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      if (data.unchanged) {
        setStatus('No changes to commit.');
        setDirty(false);
        return;
      }
      await setActiveVersion(targetBranch, data.version_id);
      if (opts.sceneNumber !== undefined) markEditedScene(opts.sceneNumber);
      await refreshRepo();
      setBranchName('');
      setCommitMsg('');
      setDirty(false);
      setStatus(`Committed ${data.version_id.slice(0, 8)} (${data.changed} change${data.changed === 1 ? '' : 's'})`);
      await loadVersion(data.version_id);
    } catch (err) {
      setStatus(`Commit failed: ${err}`);
    }
  };

  const revertTo = async (vid: string) => {
    setStatus('Reverting…');
    try {
      const res = await fetch(`/api/scripts/${scriptId}/revert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ branch_id: branchId, revert_to_version_id: vid }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      await setActiveVersion(branchId, data.version_id);
      await refreshRepo();
      setStatus(`Reverted to ${vid.slice(0, 8)} as new commit`);
    } catch (err) {
      setStatus(`Revert failed: ${err}`);
    }
  };

  // Dictation handlers — insert text into scene draft

  // Compound-utterance buffer: character/parenthetical commands accumulate here
  // until their final transcript arrives, so the whole line lands as one
  // atomic insert under a single undo entry.
  const pendingCompoundRef = useRef<string[]>([]);

  // Record snapshot undo BEFORE mutating (controlled-textarea writes destroy
  // the native Ctrl+Z stack). popUndoEntry restores the exact prior state.
  const applyInsert = useCallback(
    (insertText: string) => {
      if (!insertText) return;
      const snapshot = draftRef.current;
      pushUndoEntry({
        start: snapshot.length,
        length: insertText.length,
        snapshot,
      });
      setSceneDraft((prev) => prev + insertText);
    },
    [pushUndoEntry, setSceneDraft],
  );

  const flushCompoundBuffer = useCallback(
    (extraText: string) => {
      const buffered = pendingCompoundRef.current;
      if (buffered.length === 0 && !extraText) return;
      pendingCompoundRef.current = [];
      applyInsert(buffered.join('') + extraText);
    },
    [applyInsert],
  );

  const handleDictationTranscript = useCallback(
    (text: string, isFinal: boolean) => {
      if (!isFinal) return;
      const charCmd = targetCharacter;
      if (charCmd) {
        // Tap-to-latch: insert cue + this utterance as that character's dialogue
        flushCompoundBuffer(`\n\n${charCmd.toUpperCase()}\n${text}`);
        setTargetCharacter(null);
      } else {
        // Plain prose: newline-separate from prior content (unless a buffered
        // compound cue already ends in \n) so blocks never run together
        const buffered = pendingCompoundRef.current.length > 0;
        const sep =
          !buffered && draftRef.current && !draftRef.current.endsWith('\n') ? '\n' : '';
        flushCompoundBuffer(sep + text);
      }
      setDirty(true);
    },
    [targetCharacter, flushCompoundBuffer, setTargetCharacter, setDirty],
  );

  const handleDictationCommand = useCallback(
    (action: string, value: string, scope?: string) => {
      if (action === 'delete') {
        // "Scratch that" = discard uncommitted buffered text + undo last insert
        pendingCompoundRef.current = [];
        const draft = draftRef.current;

        if (scope === 'last_segment') {
          const entry = popUndoEntry();
          if (entry) {
            setSceneDraft(entry.snapshot);
          } else if (draft.lastIndexOf('\n\n') >= 0) {
            setSceneDraft((prev) => prev.slice(0, prev.lastIndexOf('\n\n')));
          } else {
            setSceneDraft('');
          }
        } else if (scope === 'last_sentence') {
          // Strip the trailing sentence (up to its .!? terminator) without
          // collapsing the newlines that delimit Fountain blocks
          const withoutLast = draft.replace(/[^.!?]*[.!?]\s*$/, '');
          if (withoutLast !== draft) {
            setSceneDraft(withoutLast);
          } else {
            const idx = draft.lastIndexOf('\n');
            setSceneDraft(idx >= 0 ? draft.slice(0, idx) : '');
          }
        } else if (scope === 'last_line') {
          const idx = draft.lastIndexOf('\n');
          setSceneDraft(idx >= 0 ? draft.slice(0, idx) : '');
        } else if (scope === 'last_block') {
          const idx = draft.lastIndexOf('\n\n');
          setSceneDraft(idx >= 0 ? draft.slice(0, idx) : '');
        }
        setDirty(true);
        return;
      }

      // Compound sub-commands buffer until the final transcript lands
      if (action === 'character' || action === 'parenthetical') {
        const formatted =
          action === 'character' ? `\n\n${value}\n` : `${value}\n`;
        pendingCompoundRef.current.push(formatted);
        return;
      }

      // Standalone structural commands — flush any pending buffer, then insert
      flushCompoundBuffer('');
      switch (action) {
        case 'scene_heading':
          applyInsert(`\n\n${value}\n\n`);
          break;
        case 'transition':
          applyInsert(`\n\n${value}\n\n`);
          break;
        case 'new_line':
          applyInsert('\n');
          break;
        case 'new_paragraph':
          applyInsert('\n\n');
          break;
        case 'writer_note':
          applyInsert(value);
          break;
        default:
          break; // 'action' mode switch, no text
      }
      setDirty(true);
    },
    [
      popUndoEntry,
      flushCompoundBuffer,
      applyInsert,
      setSceneDraft,
      setDirty,
    ],
  );

  // Flush any buffered compound text when dictation ends (explicit stop,
  // session expiry, disconnect) so "character X" never gets dropped.
  useEffect(() => {
    if (!dictationActive && pendingCompoundRef.current.length > 0) {
      flushCompoundBuffer('');
      setDirty(true);
    }
  }, [dictationActive, flushCompoundBuffer, setDirty]);

  const toggleDictation = async () => {
    if (dictationActive) {
      stopDictation();
      return;
    }
    if (!scriptId) return;
    const sceneNum = currentScene?.num ?? 1;
    try {
      await startDictation(scriptId, sceneNum, sceneDraft);
    } catch (err) {
      setStatus(`Dictation failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  if (!session?.loaded) {
    return (
      <WidePageContainer className="screenplay-page">
        <PageTitle className="screenplay-page-title">Screenplay</PageTitle>
        <Card padding="lg" className="screenplay-empty-card">
          <EmptyMessage className="screenplay-empty-message">
            No screenplay loaded. Pick one from the sidebar or upload in{' '}
            <InlineLink className="screenplay-inline-link" onClick={() => navigate('/workspace')}>Workspace</InlineLink>.
          </EmptyMessage>
        </Card>
      </WidePageContainer>
    );
  }

  return (
    <FullHeightContainer className="screenplay-page">
      <PageTitle className="screenplay-page-title">
        {session.title}
        <TitleSuffix className="screenplay-title-suffix">
          {session.branches.find((b) => b.branch_id === branchId)?.name}@{versionId.slice(0, 8)}
          {dirty ? ' • unsaved changes' : ''}
        </TitleSuffix>
      </PageTitle>

      <Columns sidebarWidth={sidebarCollapsed ? '56px' : '280px'} className="screenplay-columns" style={{ flex: 1, minHeight: 0 }}>
        <SceneListPanel
          scenes={sceneList}
          activeIndex={sceneIdx}
          onSelect={selectScene}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          mode={docMode}
          onModeChange={setDocMode}
        />
        <EditorColumn className="screenplay-editor-column">
          <EditorCard padding="lg" className="screenplay-editor-card">
            <SceneEditor
              scriptId={scriptId}
              sceneDraft={docMode === 'all' ? fullDraft : sceneDraft}
              setSceneDraft={docMode === 'all' ? setFullDraft : setSceneDraft}
              setDirty={setDirty}
              dictationActive={dictationActive}
              onToggleDictation={toggleDictation}
            />
          </EditorCard>
        </EditorColumn>
      </Columns>

      <TabBar className="screenplay-tab-bar">
        <TabRow className="screenplay-tab-row">
          <TabButton
            active={activeTab === 'commit' && tabsOpen}
            onClick={() => {
              setActiveTab('commit');
              setTabsOpen(true);
            }}
            className={`screenplay-tab-btn${activeTab === 'commit' && tabsOpen ? ' screenplay-tab-btn--active' : ''}`}
          >
            Commit
            {dirty && <TabDirtyDot className="screenplay-tab-dirty-dot">●</TabDirtyDot>}
          </TabButton>
          <TabButton
            active={activeTab === 'goals' && tabsOpen}
            onClick={() => {
              setActiveTab('goals');
              setTabsOpen(true);
            }}
            className={`screenplay-tab-btn${activeTab === 'goals' && tabsOpen ? ' screenplay-tab-btn--active' : ''}`}
          >
            Story Goals
          </TabButton>
          <TabButton
            active={activeTab === 'history' && tabsOpen}
            onClick={() => {
              setActiveTab('history');
              setTabsOpen(true);
            }}
            className={`screenplay-tab-btn${activeTab === 'history' && tabsOpen ? ' screenplay-tab-btn--active' : ''}`}
          >
            History &amp; Diff
          </TabButton>
          <TabCollapse
            onClick={() => setTabsOpen(!tabsOpen)}
            title={tabsOpen ? 'Collapse panels' : 'Expand panels'}
            aria-label={tabsOpen ? 'Collapse panels' : 'Expand panels'}
            className="screenplay-tabs-collapse"
          >
            {tabsOpen ? '▴' : '▾'}
          </TabCollapse>
        </TabRow>
        <TabBody open={tabsOpen} className="screenplay-tab-body">
          {activeTab === 'commit' && (
            <TabCard padding="md" className="screenplay-commit-card">
              <CommitField $reviewing={(status?.startsWith('Committing') ?? false) || (status?.startsWith('Reverting') ?? false)} className="screenplay-commit-fields">
                <CommitInput
                  placeholder="Commit message…"
                  value={commitMsg}
                  onChange={(e) => setCommitMsg(e.target.value)}
                  className="screenplay-commit-msg"
                />
                <BranchInput
                  placeholder="New branch (optional)"
                  value={branchName}
                  onChange={(e) => setBranchName(e.target.value)}
                  className="screenplay-commit-branch"
                />
                <Button onClick={docMode === 'all' ? commitFull : commitScene} disabled={!dirty}>
                  {docMode === 'all' ? 'Commit Script' : 'Commit Scene'}
                </Button>
              </CommitField>
              {status && (
                <StatusLine
                  className="screenplay-status"
                  error={status.startsWith('Commit failed') || status.startsWith('Revert failed')}
                >
                  {status}
                </StatusLine>
              )}
            </TabCard>
          )}
          {activeTab === 'goals' && (
            <TabCard padding="md" className="screenplay-goals-card">
              <GoalsPanel scriptId={session.scriptId} />
            </TabCard>
          )}
          {activeTab === 'history' && (
            <TabCard padding="md" className="screenplay-history-card">
              <Columns className="screenplay-history-columns">
                <VersionHistory
                  versions={versions}
                  branchId={branchId}
                  activeVersionId={versionId}
                  onPeek={loadVersion}
                  onRevert={revertTo}
                />
                <DiffPanel versions={versions} activeVersionId={versionId} />
              </Columns>
            </TabCard>
          )}
        </TabBody>
      </TabBar>

      <DictationOverlay
        onTranscript={handleDictationTranscript}
        onCommand={handleDictationCommand}
      />
    </FullHeightContainer>
  );
}
