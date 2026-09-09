import styled from '@emotion/styled';
import { Button } from './layout.tsx';

const Overlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
`;

const Drawer = styled.div`
  background: var(--bg-surface);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  width: 560px;
  max-height: 80vh;
  overflow-y: auto;
  padding: 24px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
`;

const Title = styled.h2`
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 16px;
  color: var(--text-primary);
`;

const Section = styled.h3`
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--accent);
  margin: 16px 0 8px;
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-bottom: 8px;

  th {
    text-align: left;
    color: var(--text-secondary);
    font-weight: 600;
    padding: 4px 8px;
    border-bottom: 1px solid var(--bg-elevated);
  }

  td {
    padding: 4px 8px;
    color: var(--text-primary);
    vertical-align: top;
  }

  td:first-child {
    font-family: var(--font-mono);
    color: var(--accent);
    white-space: nowrap;
  }
`;

const Code = styled.pre`
  background: var(--bg-elevated);
  border-radius: 4px;
  padding: 10px 12px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  margin: 0 0 8px;
  color: var(--text-primary);
`;

const CloseRow = styled.div`
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
`;

interface FountainCheatSheetProps {
  onClose: () => void;
}

export function FountainCheatSheet({ onClose }: FountainCheatSheetProps) {
  return (
    <Overlay className="fountain-cheatsheet-overlay" onClick={onClose}>
      <Drawer className="fountain-cheatsheet" onClick={(e) => e.stopPropagation()}>
        <Title className="fountain-cheatsheet-title">Fountain Syntax Reference</Title>

        <Section className="fountain-cheatsheet-section">Title Page</Section>
        <Code className="fountain-cheatsheet-code">{`Title: NEON RUNNER
Credit: Written by
Author: Alex Vance
Draft date: 2026-08-26
Contact: agent@cyberpunk-studio.io`}</Code>

        <Section className="fountain-cheatsheet-section">Screenplay Elements</Section>
        <Table className="fountain-cheatsheet-table">
          <thead>
            <tr><th>Syntax</th><th>Element</th></tr>
          </thead>
          <tbody>
            <tr><td>INT. / EXT.</td><td>Scene heading (slugline)</td></tr>
            <tr><td>.HEADING</td><td>Forced slugline (non-standard)</td></tr>
            <tr><td>UPPERCASE</td><td>Character cue</td></tr>
            <tr><td>(whispering)</td><td>Parenthetical</td></tr>
            <tr><td>&gt;CUT TO:&lt;</td><td>Transition</td></tr>
            <tr><td>!ACTION</td><td>Forced action line</td></tr>
            <tr><td>~lyrics~</td><td>Lyrics</td></tr>
            <tr><td>&gt;text&lt;</td><td>Centered text</td></tr>
            <tr><td># Section</td><td>Section header (act/beat)</td></tr>
            <tr><td>= synopsis</td><td>Synopsis line</td></tr>
          </tbody>
        </Table>

        <Section className="fountain-cheatsheet-section">Inline Styling</Section>
        <Table className="fountain-cheatsheet-table">
          <thead>
            <tr><th>Syntax</th><th>Result</th></tr>
          </thead>
          <tbody>
            <tr><td>**bold**</td><td>Bold</td></tr>
            <tr><td>*italic*</td><td>Italic</td></tr>
            <tr><td>_underline_</td><td>Underline</td></tr>
            <tr><td>***bold italic***</td><td>Bold &amp; Italic</td></tr>
          </tbody>
        </Table>

        <Section className="fountain-cheatsheet-section">Notes &amp; Omissions</Section>
        <Table className="fountain-cheatsheet-table">
          <thead>
            <tr><th>Syntax</th><th>Purpose</th></tr>
          </thead>
          <tbody>
            <tr><td>[[note]]</td><td>Internal note (hidden in print)</td></tr>
            <tr><td>[...]</td><td>Omitted text</td></tr>
            <tr><td>/* block */</td><td>Comment / boneyard (hidden)</td></tr>
          </tbody>
        </Table>

        <Section className="fountain-cheatsheet-section">Example</Section>
        <Code className="fountain-cheatsheet-code">{`INT. CONTROL ROOM - NIGHT
        
KAEL
(whispering)
We've got thirty seconds.

He types furiously. [[Add password prompt here]]

SMASH CUT TO:

EXT. ROOFTOP - RAIN

Kael sprints across wet gravel.`}</Code>

        <CloseRow className="fountain-cheatsheet-close-row">
          <Button onClick={onClose}>Close</Button>
        </CloseRow>
      </Drawer>
    </Overlay>
  );
}
