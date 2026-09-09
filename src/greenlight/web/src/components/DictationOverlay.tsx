import { useEffect, useCallback } from 'react';
import styled from '@emotion/styled';
import { useDictationStore } from '../lib/store-dictation';

const Overlay = styled.div<{ $visible: boolean }>`
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  display: ${({ $visible }) => ($visible ? 'flex' : 'none')};
  flex-direction: column;
  align-items: center;
  gap: 8px;
  background: var(--bg-elevated, #1a1a2e);
  border: 1px solid var(--border, #333);
  border-radius: 12px;
  padding: 12px 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  min-width: 360px;
  font-family: var(--font-mono, monospace);
`;

const TopRow = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
`;

const RecDot = styled.div<{ $recording: boolean }>`
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: ${({ $recording }) => ($recording ? '#ff3b3b' : '#666')};
  animation: ${({ $recording }) =>
    $recording ? 'pulse 1.5s ease-in-out infinite' : 'none'};

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
`;

const VUMeter = styled.div<{ $level: number }>`
  flex: 1;
  height: 6px;
  background: var(--bg-muted, #2a2a3e);
  border-radius: 3px;
  overflow: hidden;

  &::after {
    content: '';
    display: block;
    width: ${({ $level }) => Math.min(100, $level * 300)}%;
    height: 100%;
    background: ${({ $level }) =>
      $level > 0.8 ? '#ff6b6b' : $level > 0.4 ? '#ffd93d' : '#6bcb77'};
    border-radius: 3px;
    transition: width 0.08s linear;
  }
`;

const Timer = styled.span`
  font-size: 12px;
  color: var(--text-secondary, #888);
  white-space: nowrap;
`;

const InterimText = styled.div`
  font-size: 13px;
  color: var(--text-primary, #ccc);
  font-style: italic;
  text-align: center;
  min-height: 18px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const CharacterRow = styled.div`
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: center;
`;

const CharBadge = styled.button<{ $active: boolean }>`
  background: ${({ $active }) =>
    $active ? 'var(--accent, #4ecdc4)' : 'var(--bg-muted, #2a2a3e)'};
  color: ${({ $active }) => ($active ? '#000' : 'var(--text-secondary, #888)')};
  border: 1px solid
    ${({ $active }) => ($active ? 'var(--accent, #4ecdc4)' : 'var(--border, #333)')};
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    border-color: var(--accent, #4ecdc4);
    color: var(--text-primary, #ccc);
  }
`;

const Warning = styled.div`
  font-size: 11px;
  color: #ffd93d;
  text-align: center;
`;

const StopButton = styled.button`
  background: var(--danger, #ff6b6b);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;

  &:hover {
    opacity: 0.85;
  }
`;

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

interface DictationOverlayProps {
  onTranscript?: (text: string, isFinal: boolean) => void;
  onCommand?: (action: string, value: string, scope?: string) => void;
}

export function DictationOverlay({ onTranscript, onCommand }: DictationOverlayProps) {
  const session = useDictationStore((s) => s.session);
  const interimText = useDictationStore((s) => s.interimText);
  const vuMeter = useDictationStore((s) => s.vuMeter);
  const remainingSeconds = useDictationStore((s) => s.remainingSeconds);
  const targetCharacter = useDictationStore((s) => s.targetCharacter);
  const stopDictation = useDictationStore((s) => s.stopDictation);
  const setTargetCharacter = useDictationStore((s) => s.setTargetCharacter);

  const visible = session?.active ?? false;

  // Handle tap-latch keys 1–9
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!visible) return;
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      if (e.code >= 'Digit1' && e.code <= 'Digit9') {
        const idx = parseInt(e.code.replace('Digit', ''), 10) - 1;
        const chars = session?.characters ?? [];
        if (idx < chars.length) {
          const name = chars[idx];
          // Toggle latch: tap same key again to clear
          setTargetCharacter(targetCharacter === name ? null : name);
        }
      }

      // Escape clears latch
      if (e.code === 'Escape') {
        setTargetCharacter(null);
      }
    },
    [visible, session?.characters, targetCharacter, setTargetCharacter],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Delegate transcript/command events to parent
  useEffect(() => {
    if (!visible) return;

    const handler = (event: Event) => {
      const data = (event as CustomEvent).detail;
      if (!data) return;
      if (data.type === 'transcript' && data.is_final) {
        onTranscript?.(data.text, true);
      } else if (data.type === 'transcript') {
        onTranscript?.(data.text, false);
      } else if (data.type === 'command') {
        onCommand?.(data.action, data.value, data.scope);
      }
    };

    // Store dispatches 'dictation-message' CustomEvent for transcript/command frames
    window.addEventListener('dictation-message', handler);
    return () => window.removeEventListener('dictation-message', handler);
  }, [visible, onTranscript, onCommand]);

  return (
    <Overlay $visible={visible} className="dictation-overlay">
      <TopRow className="dictation-overlay-top-row">
        <RecDot $recording={visible} className="dictation-overlay-rec-dot" />
        <VUMeter $level={vuMeter} className="dictation-overlay-vu-meter" />
        <Timer className="dictation-overlay-timer">{formatTime(remainingSeconds)}</Timer>
      </TopRow>

      {interimText && <InterimText className="dictation-overlay-interim">"{interimText}"</InterimText>}

      {session?.characters && session.characters.length > 0 && (
        <CharacterRow className="dictation-overlay-characters">
          {session.characters.map((name, i) => (
            <CharBadge
              key={name}
              $active={targetCharacter === name}
              onClick={() =>
                setTargetCharacter(targetCharacter === name ? null : name)
              }
              title={`Press ${i + 1} to latch`}
              className={`dictation-overlay-char-badge${targetCharacter === name ? ' dictation-overlay-char-badge--active' : ''}`}
            >
              {i + 1} {name}
            </CharBadge>
          ))}
        </CharacterRow>
      )}

      {session?.stoplistCollisions && session.stoplistCollisions.length > 0 && (
        <Warning className="dictation-overlay-warning">
          ⚠ {session.stoplistCollisions.join(', ')} may not auto-cap (common word)
        </Warning>
      )}

      <StopButton className="dictation-overlay-stop" onClick={stopDictation}>Stop Dictation</StopButton>
    </Overlay>
  );
}
