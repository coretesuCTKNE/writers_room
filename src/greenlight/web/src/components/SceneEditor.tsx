import styled from '@emotion/styled';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Card, FountainPreview } from '../components';
import { FountainCheatSheet } from './FountainCheatSheet';
import { Button, Row } from '../components/layout.tsx';
import { lintFountain } from '../lib/fountainLint';

const LINE_NUMBERS_KEY = 'screenplay.lineNumbers';
const TOOLS_COLLAPSED_KEY = 'screenplay.toolsCollapsed';

const EditorWrap = styled.div`
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
`;

const EditorLayout = styled.div`
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
`;

const EditorGrid = styled.div<{ mode: ViewMode }>`
  display: grid;
  gap: 16px;
  align-items: stretch;
  grid-template-columns: ${({ mode }) =>
    mode === 'both' ? '1fr 1fr' : '1fr'};
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
`;

const PaneColumn = styled.div`
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
`;

const PreviewScroll = styled.div`
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  border-radius: var(--radius);
`;

const RailCard = styled(Card)<{ collapsed: boolean }>`
  flex-shrink: 0;
  width: ${({ collapsed }) => (collapsed ? '48px' : '264px')};
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  transition: width 0.25s ease;
`;

const RailScroll = styled.div`
  overflow-y: auto;
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const RailHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  min-height: 22px;
  gap: 8px;
`;

const RailTitle = styled.div`
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-secondary);
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

const RailActions = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const Divider = styled.div`
  height: 1px;
  background: var(--bg-elevated);
`;

const ModeToggle = styled.div`
  display: inline-flex;
  background: var(--bg-elevated);
  border-radius: var(--radius);
  padding: 3px;
  gap: 2px;
`;

const ModeButton = styled.button<{ active?: boolean }>`
  padding: 5px 12px;
  background: ${({ active }) => (active ? 'var(--accent)' : 'transparent')};
  color: ${({ active }) => (active ? 'var(--bg-base)' : 'var(--text-secondary)')};
  border: none;
  border-radius: calc(var(--radius) - 3px);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition);

  &:hover {
    color: ${({ active }) => (active ? 'var(--bg-base)' : 'var(--text-primary)')};
  }
`;

const PaneLabel = styled.div`
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-secondary);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const EditorArea = styled.textarea`
  flex: 1;
  width: 100%;
  min-height: 0;
  padding: 14px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  resize: none;
  tab-size: 4;
  overflow-y: auto;

  &:focus {
    outline: none;
    border-color: var(--accent);
  }
`;

const EditorWithLineNumbers = styled.div`
  flex: 1;
  display: flex;
  position: relative;
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  background: var(--bg-elevated);
  overflow: hidden;
  min-height: 0;
`;

const LineNumberGutter = styled.div`
  width: 40px;
  padding: 14px 0;
  background: var(--bg-elevated);
  border-right: 1px solid var(--bg-elevated);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  text-align: right;
  user-select: none;
  overflow: hidden;
  flex-shrink: 0;
`;

const LineNumber = styled.div`
  padding-right: 8px;
  height: 1.6em;
`;

const EditorAreaWithNumbers = styled(EditorArea)`
  border: none;
  border-radius: 0;
  padding-left: 10px;
`;

const Tip = styled.div`
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
`;

const InlineCode = styled.code`
  color: var(--accent);
`;

const LintStrip = styled.div<{ clean: boolean }>`
  font-size: 12px;
  line-height: 1.5;
  margin-top: auto;
  color: ${({ clean }) => (clean ? 'var(--text-secondary)' : 'var(--accent)')};
`;

const CollapsedRail = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
`;

const CollapsedItem = styled.button<{ active?: boolean; $danger?: boolean }>`
  width: 32px;
  height: 32px;
  border-radius: 4px;
  background: ${({ active, $danger }) =>
    $danger ? 'var(--danger)' : active ? 'rgba(50, 205, 50, 0.18)' : 'var(--bg-elevated)'};
  border: 1px solid ${({ active, $danger }) =>
    $danger ? 'var(--danger)' : active ? 'var(--accent)' : 'var(--bg-elevated)'};
  color: ${({ active, $danger }) =>
    $danger ? '#fff' : active ? 'var(--accent)' : 'var(--text-secondary)'};
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;

  &:hover {
    border-color: var(--accent);
  }
`;

const MicButton = styled.button<{ $active: boolean }>`
  width: 100%;
  background: ${({ $active }) => ($active ? 'var(--danger)' : 'var(--bg-elevated)')};
  color: ${({ $active }) => ($active ? '#fff' : 'var(--text-secondary)')};
  border: 1px solid ${({ $active }) => ($active ? 'var(--danger)' : 'var(--border)')};
  border-radius: var(--radius);
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.15s ease;

  &:hover {
    border-color: var(--accent);
    color: var(--text-primary);
  }
  &:hover:not(:disabled) {
    opacity: 0.9;
    border-color: var(--accent);
  }
`;

type ViewMode = 'source' | 'preview' | 'both';

const VIEW_MODE_KEY = 'screenplay.viewMode';

interface SceneEditorProps {
  scriptId: string;
  sceneDraft: string;
  setSceneDraft: (v: string) => void;
  setDirty: (d: boolean) => void;
  dictationActive: boolean;
  onToggleDictation: () => void;
}

export function SceneEditor({
  scriptId,
  sceneDraft,
  setSceneDraft,
  setDirty,
  dictationActive,
  onToggleDictation,
}: SceneEditorProps) {
  const [viewMode, setViewMode] = useStateViewMode();
  const [showCheatSheet, setShowCheatSheet] = useState(false);
  const [showLineNumbers, setShowLineNumbers] = useStateLineNumbers();
  const [toolsCollapsed, setToolsCollapsed] = useStateToolsCollapsed();
  const [beautifying, setBeautifying] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);

  const lineCount = sceneDraft.split('\n').length;
  const lintIssues = useMemo(() => lintFountain(sceneDraft), [sceneDraft]);

  const handleBeautify = async () => {
    setBeautifying(true);
    try {
      const res = await fetch('/api/screenplay/beautify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: sceneDraft }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.changed) {
        setSceneDraft(data.text);
        setDirty(true);
      }
    } catch {
      /* beautify is best-effort */
    } finally {
      setBeautifying(false);
    }
  };

  const handleScroll = useCallback(() => {
    if (textareaRef.current && gutterRef.current) {
      gutterRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  }, []);

  const handleExport = async () => {
    try {
      const res = await fetch(`/api/scripts/${scriptId}/text`);
      if (!res.ok) return;
      const text = await res.text();
      const blob = new Blob([text], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${scriptId}.fountain`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      /* silent fail */
    }
  };

  return (
    <>
      <EditorWrap className="scene-editor-wrap">
        <EditorLayout className="scene-editor-layout">
          <EditorGrid mode={viewMode} className="scene-editor-grid">
            {viewMode !== 'preview' && (
              <PaneColumn className="scene-editor-pane">
                <PaneLabel className="scene-editor-pane-label">
                  Fountain Source
                  <ModeToggle className="scene-editor-mode-toggle">
                    <ModeButton active={viewMode === 'source'} onClick={() => setViewMode('source')} className={`scene-editor-mode-btn${viewMode === 'source' ? ' scene-editor-mode-btn--active' : ''}`}>
                      Raw
                    </ModeButton>
                    <ModeButton active={viewMode === 'both'} onClick={() => setViewMode('both')} className={`scene-editor-mode-btn${viewMode === 'both' ? ' scene-editor-mode-btn--active' : ''}`}>
                      Split
                    </ModeButton>
                  </ModeToggle>
                </PaneLabel>
                {showLineNumbers ? (
                  <EditorWithLineNumbers className="scene-editor-textarea-with-numbers">
                    <LineNumberGutter ref={gutterRef} className="scene-editor-line-gutter">
                      {Array.from({ length: lineCount }, (_, i) => (
                        <LineNumber key={i} className="scene-editor-line-number">{i + 1}</LineNumber>
                      ))}
                    </LineNumberGutter>
                    <EditorAreaWithNumbers
                      ref={textareaRef}
                      value={sceneDraft}
                      onChange={(e) => {
                        setSceneDraft(e.target.value);
                        setDirty(true);
                      }}
                      onScroll={handleScroll}
                      className="scene-editor-textarea"
                    />
                  </EditorWithLineNumbers>
                ) : (
                  <EditorArea
                    value={sceneDraft}
                    onChange={(e) => {
                      setSceneDraft(e.target.value);
                      setDirty(true);
                    }}
                    className="scene-editor-textarea"
                  />
                )}
              </PaneColumn>
            )}
            {viewMode !== 'source' && (
              <PaneColumn className="scene-editor-pane">
                <PaneLabel className="scene-editor-pane-label">
                  Preview
                  <ModeToggle className="scene-editor-mode-toggle">
                    <ModeButton active={viewMode === 'preview'} onClick={() => setViewMode('preview')} className={`scene-editor-mode-btn${viewMode === 'preview' ? ' scene-editor-mode-btn--active' : ''}`}>
                      Preview
                    </ModeButton>
                    <ModeButton active={viewMode === 'both'} onClick={() => setViewMode('both')} className={`scene-editor-mode-btn${viewMode === 'both' ? ' scene-editor-mode-btn--active' : ''}`}>
                      Split
                    </ModeButton>
                  </ModeToggle>
                </PaneLabel>
                <PreviewScroll className="scene-editor-preview-scroll">
                  <FountainPreview script={sceneDraft} />
                </PreviewScroll>
              </PaneColumn>
            )}
          </EditorGrid>

          <RailCard collapsed={toolsCollapsed} padding="md" className="scene-editor-tools-rail">
            <RailHeader className="scene-editor-tools-header">
              {!toolsCollapsed && <RailTitle className="scene-editor-tools-title">Tools</RailTitle>}
              {toolsCollapsed && <span />}
              <ToggleButton
                onClick={() => setToolsCollapsed(!toolsCollapsed)}
                title={toolsCollapsed ? 'Expand tools' : 'Collapse tools'}
                aria-label={toolsCollapsed ? 'Expand tools' : 'Collapse tools'}
                className="scene-editor-tools-toggle"
              >
                {toolsCollapsed ? '‹' : '›'}
              </ToggleButton>
            </RailHeader>

            {toolsCollapsed ? (
              <RailScroll className="scene-editor-tools-collapsed">
                <CollapsedRail className="scene-editor-tools-collapsed-rail">
                  <CollapsedItem
                    $danger={dictationActive}
                    onClick={onToggleDictation}
                    title={dictationActive ? 'Stop dictate' : 'Dictate'}
                    aria-label={dictationActive ? 'Stop dictate' : 'Dictate'}
                    className="scene-editor-tools-collapsed-mic"
                  >
                    🎙
                  </CollapsedItem>
                  <CollapsedItem onClick={handleExport} title="Export .fountain" className="scene-editor-tools-collapsed-export">↓</CollapsedItem>
                  <CollapsedItem onClick={handleBeautify} disabled={beautifying} title="Beautify" className="scene-editor-tools-collapsed-beautify">✦</CollapsedItem>
                  <CollapsedItem onClick={() => setShowCheatSheet(true)} title="Fountain syntax help" className="scene-editor-tools-collapsed-help">?</CollapsedItem>
                  <CollapsedItem active={showLineNumbers} onClick={() => setShowLineNumbers(!showLineNumbers)} title="Toggle line numbers" className="scene-editor-tools-collapsed-lines">#</CollapsedItem>
                </CollapsedRail>
              </RailScroll>
            ) : (
              <RailScroll className="scene-editor-tools-body">
                <MicButton
                  $active={dictationActive}
                  onClick={onToggleDictation}
                  className="scene-editor-mic-btn"
                >
                  {dictationActive ? '■ Stop Dictating' : '🎙 Dictate'}
                </MicButton>
                <RailActions className="scene-editor-tools-actions">
                  <Button variant="ghost" onClick={handleExport} className="scene-editor-export-btn">
                    Export .fountain
                  </Button>
                  <Button variant="ghost" onClick={handleBeautify} disabled={beautifying} className="scene-editor-beautify-btn">
                    {beautifying ? 'Beautifying…' : 'Beautify'}
                  </Button>
                  <Row className="scene-editor-tools-row">
                    <Button variant="ghost" onClick={() => setShowCheatSheet(true)}>
                      ?
                    </Button>
                    <Button
                      variant={showLineNumbers ? 'primary' : 'ghost'}
                      onClick={() => setShowLineNumbers(!showLineNumbers)}
                    >
                      #
                    </Button>
                  </Row>
                </RailActions>

                <Divider />

                <LintStrip clean={lintIssues.length === 0} className="scene-editor-lint">
                  {lintIssues.length === 0
                    ? 'Formatting looks clean.'
                    : lintIssues
                        .slice(0, 2)
                        .map((i) => `Line ${i.line}: ${i.message}`)
                        .join(' · ') + (lintIssues.length > 2 ? ` (+${lintIssues.length - 2} more)` : '')}
                </LintStrip>

                <Tip className="scene-editor-tip">
                  Add an <InlineCode>INT. / EXT.</InlineCode> heading line to split or insert
                  scenes — they&apos;re created on commit. Clearing the whole draft deletes it.
                </Tip>
              </RailScroll>
            )}
          </RailCard>
        </EditorLayout>
        {showCheatSheet && <FountainCheatSheet onClose={() => setShowCheatSheet(false)} />}
      </EditorWrap>
    </>
  );
}

function useStateViewMode(): [ViewMode, (m: ViewMode) => void] {
  const [mode, setMode] = useState<ViewMode>(
    () => (localStorage.getItem(VIEW_MODE_KEY) as ViewMode) || 'both',
  );
  useEffect(() => {
    localStorage.setItem(VIEW_MODE_KEY, mode);
  }, [mode]);
  return [mode, setMode];
}

function useStateLineNumbers(): [boolean, (v: boolean) => void] {
  const [on, setOn] = useState<boolean>(
    () => localStorage.getItem(LINE_NUMBERS_KEY) === 'true',
  );
  useEffect(() => {
    localStorage.setItem(LINE_NUMBERS_KEY, String(on));
  }, [on]);
  return [on, setOn];
}

function useStateToolsCollapsed(): [boolean, (v: boolean) => void] {
  const [on, setOn] = useState<boolean>(
    () => localStorage.getItem(TOOLS_COLLAPSED_KEY) === 'true',
  );
  useEffect(() => {
    localStorage.setItem(TOOLS_COLLAPSED_KEY, String(on));
  }, [on]);
  return [on, setOn];
}