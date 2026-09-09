import styled from '@emotion/styled';
import ReactMarkdown from 'react-markdown';
import type { AgentRun } from '../../lib/types';

/** Extract the persisted agent response text from an AgentRun.result. */
export function agentRunResponse(run: AgentRun): string {
  const res = run.result as unknown;
  if (typeof res === 'string') return res;
  if (res && typeof res === 'object') {
    const obj = res as Record<string, unknown>;
    if (typeof obj.response === 'string') return obj.response;
    if (typeof obj.error === 'string') return obj.error;
  }
  return '';
}

export const MarkdownResult = styled.div`
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-elevated);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  font-size: 13px;
  line-height: 1.6;
  max-height: 320px;
  overflow-y: auto;

  h1,
  h2,
  h3 {
    font-size: 14px;
    margin: 12px 0 6px;
    color: var(--text-primary);
    &:first-of-type {
      margin-top: 0;
    }
  }

  p {
    margin: 6px 0;
  }

  ul,
  ol {
    margin: 6px 0;
    padding-left: 18px;
  }

  li {
    margin: 3px 0;
  }

  code {
    background: var(--bg-base);
    padding: 1px 4px;
    border-radius: 4px;
    font-size: 12px;
  }

  pre {
    background: var(--bg-base);
    padding: 10px;
    border-radius: var(--radius);
    overflow-x: auto;
    code {
      background: none;
      padding: 0;
    }
  }

  strong {
    color: var(--text-primary);
  }

  a {
    color: var(--accent);
  }
`;

interface MarkdownBoxProps {
  children: string;
  header?: string;
}

export function MarkdownBox({ children, header }: MarkdownBoxProps) {
  return (
    <MarkdownResult className="agent-markdown-result">
      {header && (
        <>
          <strong>{header}</strong>
          <br />
        </>
      )}
      <ReactMarkdown>{children}</ReactMarkdown>
    </MarkdownResult>
  );
}
