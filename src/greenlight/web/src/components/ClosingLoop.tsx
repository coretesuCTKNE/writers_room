import styled from '@emotion/styled';

const Container = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
  height: 100%;
`;

const Pane = styled.div`
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  overflow: hidden;
`;

const PaneHeader = styled.div`
  padding: 12px 16px;
  background: var(--bg-elevated);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--bg-elevated);
`;

const PaneBody = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 16px;
`;

const TranscriptLine = styled.div`
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  font-family: var(--font-display);
  font-size: 13px;
`;

const Speaker = styled.span`
  font-weight: 700;
  color: var(--accent);
  margin-right: 8px;
  font-size: 11px;
  text-transform: uppercase;
`;

const ScriptLine = styled.div`
  padding: 6px 0;
  font-family: var(--font-display);
  font-size: 13px;
  line-height: 1.6;
`;

const Parenthetical = styled.span`
  color: var(--accent);
  font-style: italic;
`;

const AudioPlaceholder = styled.div`
  padding: 24px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
`;

interface Turn {
  speaker: string;
  transcript: string;
  prosody_tags?: string[];
}

interface ClosingLoopProps {
  turns: Turn[];
  audioUrl?: string;
}

export function ClosingLoop({ turns, audioUrl }: ClosingLoopProps) {
  const enrichedScript = turns.map((turn) => {
    const tags = turn.prosody_tags?.length
      ? turn.prosody_tags.map((t) => `(${t})`).join(' ')
      : '';
    return {
      speaker: turn.speaker,
      text: tags ? `${tags} ${turn.transcript}` : turn.transcript,
      hasParenthetical: !!tags,
      tags,
    };
  });

  return (
    <Container className="closing-loop">
      <Pane className="closing-loop-pane">
        <PaneHeader className="closing-loop-pane-header">What You Said</PaneHeader>
        <PaneBody className="closing-loop-pane-body">
          {turns.map((turn, i) => (
            <TranscriptLine key={i} className="closing-loop-transcript-line">
              <Speaker className="closing-loop-speaker">{turn.speaker}</Speaker>
              {turn.transcript}
            </TranscriptLine>
          ))}
        </PaneBody>
      </Pane>

      <Pane className="closing-loop-pane">
        <PaneHeader className="closing-loop-pane-header">What Was Written</PaneHeader>
        <PaneBody className="closing-loop-pane-body">
          {enrichedScript.map((line, i) => (
            <ScriptLine key={i} className="closing-loop-script-line">
              <Speaker className="closing-loop-speaker">{line.speaker}</Speaker>
              {line.hasParenthetical ? (
                <>
                  <Parenthetical className="closing-loop-parenthetical">{line.tags} </Parenthetical>
                  {line.text.replace(line.tags + ' ', '')}
                </>
              ) : (
                line.text
              )}
            </ScriptLine>
          ))}
        </PaneBody>
      </Pane>

      <Pane className="closing-loop-pane">
        <PaneHeader className="closing-loop-pane-header">What Got Performed</PaneHeader>
        <PaneBody className="closing-loop-pane-body">
          {audioUrl ? (
            <AudioPlaceholder className="closing-loop-audio">
              <audio controls src={audioUrl} className="closing-loop-audio-player" style={{ width: '100%' }} />
              <div className="closing-loop-audio-note" style={{ marginTop: '12px' }}>TTS with prosody tags</div>
            </AudioPlaceholder>
          ) : (
            <AudioPlaceholder className="closing-loop-audio-empty">
              TTS audio will appear here after prosody extraction.
            </AudioPlaceholder>
          )}
        </PaneBody>
      </Pane>
    </Container>
  );
}
