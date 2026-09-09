import { useEffect, useMemo, useState } from 'react';
import styled from '@emotion/styled';
// @ts-expect-error no types shipped for aw-parser
import { parser } from 'aw-parser';

const Page = styled.div`
  background: #fdfcf8;
  color: #222;
  font-family: 'Courier New', Courier, monospace;
  font-size: 14px;
  line-height: 1.45;
  padding: 40px 48px;
  border-radius: var(--radius);
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
`;

const Line = styled.div<{ kind: string }>`
  white-space: pre-wrap;
  margin-bottom: ${({ kind }) =>
    kind === 'scene_heading' || kind === 'action' || kind === 'transition' ? '16px' : '0'};

  ${({ kind }) => {
    switch (kind) {
      case 'scene_heading':
        return `
          text-transform: uppercase;
          font-weight: 700;
          text-decoration: underline;
        `;
      case 'character':
        return `
          text-transform: uppercase;
          margin-left: 38%;
          margin-top: 12px;
        `;
      case 'parenthetical':
        return `margin-left: 32%;`;
      case 'dialogue':
        return `
          margin-left: 18%;
          margin-right: 18%;
        `;
      case 'transition':
        return `
          text-transform: uppercase;
          text-align: right;
        `;
      case 'centered':
        return `text-align: center;`;
      case 'shot':
        return `
          text-transform: uppercase;
          font-weight: 700;
        `;
      case 'note':
        return `
          color: #8a7f66;
          font-style: italic;
        `;
      case 'synopsis':
      case 'section':
        return `
          color: #8a7f66;
          font-style: italic;
        `;
      default:
        return '';
    }
  }}
`;

const EmptyPage = styled(Page)`
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b3aa93;
`;

interface Token {
  type: string;
  text: string;
}

export function FountainPreview({ script }: { script: string }) {
  const [debouncedScript, setDebouncedScript] = useState(script);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedScript(script), 150);
    return () => clearTimeout(t);
  }, [script]);

  const stripped = useMemo(
    () =>
      debouncedScript
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/\[\[[\s\S]*?\]\]/g, ''),
    [debouncedScript],
  );

  const lines = useMemo(() => {
    if (!stripped.trim()) return null;
    try {
      const result = parser.parse(stripped, {
        print_notes: true,
        print_actions: true,
        print_headers: true,
        print_dialogues: true,
        merge_multiple_empty_lines: false,
      });
      return (result.tokens as Token[])
        .filter((t) => t.type !== 'separator' && t.text.trim() !== '')
        .map((t, i) => ({ id: i, type: t.type, text: t.text }));
    } catch {
      return [{ id: -1, type: 'action', text: stripped }];
    }
  }, [stripped]);

  if (!lines) {
    return <EmptyPage className="fountain-preview fountain-preview--empty">Nothing to preview</EmptyPage>;
  }

  return (
    <Page className="fountain-preview">
      {lines.map((l) => (
        <Line
          key={l.id}
          kind={l.type}
          className={`fountain-preview-line fountain-preview-line--${l.type}`}
        >
          {l.text}
        </Line>
      ))}
    </Page>
  );
}
