import { useEffect, useState } from 'react';
import styled from '@emotion/styled';
import { useLocation } from 'react-router-dom';
import { Card, Chip } from '../components';
import { Button, ErrorText, PageContainer, PageTitle } from '../components/layout.tsx';
import { useProjectStore } from '../lib/store-project';
import type { CoverageData } from '../lib/types';

const Subtitle = styled.div`
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 24px;
`;

const Section = styled.section`
  margin-bottom: 32px;
`;

const SectionTitle = styled.h2`
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const MetaRow = styled.div`
  display: flex;
  gap: 24px;
  align-items: center;
  margin-bottom: 24px;
  font-size: 13px;
  color: var(--text-secondary);
  flex-wrap: wrap;
`;

const CommentsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
`;

const Body = styled.p`
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  margin: 0;
`;

const LoadingText = styled.p`
  color: var(--text-secondary);
`;

const HelperText = styled.p`
  color: var(--text-secondary);
`;

const ChipRow = styled.div`
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
`;

interface CommentCardProps {
  title: string;
  body: string;
}

function CommentCard({ title, body }: CommentCardProps) {
  if (!body) return null;
  return (
    <Card padding="md" className="coverage-comment-card">
      <SectionTitle className="coverage-comment-title">{title}</SectionTitle>
      <Body className="coverage-comment-body">{body}</Body>
    </Card>
  );
}

export function CoveragePage() {
  const session = useProjectStore((s) => s.session);
  const location = useLocation();
  const [coverage, setCoverage] = useState<CoverageData | null>(
    () => (location.state as { coverage?: CoverageData } | null)?.coverage ?? null,
  );
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleRunCoverage = async () => {
    if (!session?.loaded || !session.scriptId) return;
    setRunning(true);
    setErrorMsg(null);
    try {
      const textRes = await fetch(`/api/scripts/${session.scriptId}/text`);
      if (!textRes.ok) throw new Error('Script text not found');
      const scriptText = await textRes.text();

      const coverageRes = await fetch(`/api/scripts/${session.scriptId}/coverage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script_text: scriptText }),
      });
      if (!coverageRes.ok) {
        const detail = await coverageRes.json().catch(() => null);
        throw new Error(detail?.detail ?? `Coverage failed (HTTP ${coverageRes.status})`);
      }

      const coverage = await coverageRes.json();
      setNotFound(false);
      setCoverage(coverage);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => {
    if (coverage || !session?.loaded) return;
    setLoading(true);
    setErrorMsg(null);
    fetch(`/api/scripts/${session.scriptId}/coverage/latest`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: CoverageData & { found?: boolean }) => {
        if (data.found === false) {
          setNotFound(true);
          return;
        }
        setCoverage(data);
      })
      .catch((err: Error) => {
        setErrorMsg(err.message);
        setNotFound(true);
      })
      .finally(() => setLoading(false));
  }, [coverage, session?.loaded, session?.scriptId]);

  if (!coverage) {
    const noScript = !session?.loaded;
    return (
      <PageContainer className="coverage-page">
        <PageTitle className="coverage-page-title">Coverage</PageTitle>
        <Card padding="lg" className="coverage-empty-card">
          {loading ? (
            <LoadingText className="coverage-loading-text">Loading coverage…</LoadingText>
          ) : noScript ? (
            <HelperText className="coverage-helper-text">
              No screenplay loaded. Load one from the sidebar, then run coverage from Workspace.
            </HelperText>
          ) : notFound ? (
            <>
              <HelperText className="coverage-helper-text">
                No coverage run yet for <strong>{session?.title}</strong>.
              </HelperText>
              {errorMsg && <ErrorText>{errorMsg}</ErrorText>}
              <Button
                variant="primary"
                onClick={handleRunCoverage}
                disabled={running}
                style={{ marginTop: 8 }}
              >
                {running ? '⏳ Running…' : 'Run Coverage'}
              </Button>
            </>
          ) : null}
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer className="coverage-page">
      <PageTitle className="coverage-page-title">{coverage.title || 'Coverage'}</PageTitle>
      <Subtitle className="coverage-subtitle">
        Reader verdict: <strong>{coverage.verdict || 'CONSIDER'}</strong>
        {coverage.source && <> · source: {coverage.source}</>}
      </Subtitle>
      <MetaRow className="coverage-meta-row">
        {coverage.created_at && <span>Generated {coverage.created_at}</span>}
        {coverage.coverage_id && <span>ID: {coverage.coverage_id}</span>}
      </MetaRow>

      {coverage.logline && (
        <Section className="coverage-section">
          <SectionTitle className="coverage-section-title">Logline</SectionTitle>
          <Card padding="md" className="coverage-logline-card">
            <Body className="coverage-body">{coverage.logline}</Body>
          </Card>
        </Section>
      )}

      {coverage.synopsis && (
        <Section className="coverage-section">
          <SectionTitle className="coverage-section-title">Synopsis</SectionTitle>
          <Card padding="md" className="coverage-synopsis-card">
            <Body className="coverage-body">{coverage.synopsis}</Body>
          </Card>
        </Section>
      )}

      {coverage.comments && Object.keys(coverage.comments).length > 0 && (
        <Section className="coverage-section">
          <SectionTitle className="coverage-section-title">Comments</SectionTitle>
          <CommentsGrid className="coverage-comments-grid">
            <CommentCard title="Plot" body={coverage.comments.plot || ''} />
            <CommentCard title="Character" body={coverage.comments.character || ''} />
            <CommentCard title="Dialogue" body={coverage.comments.dialogue || ''} />
            <CommentCard title="Structure" body={coverage.comments.structure || ''} />
            <CommentCard title="Marketability" body={coverage.comments.marketability || ''} />
          </CommentsGrid>
        </Section>
      )}

      {coverage.analyst_notes && (
        <Section className="coverage-section">
          <SectionTitle className="coverage-section-title">Analyst Notes</SectionTitle>
          <Card padding="md" className="coverage-analyst-notes-card">
            <Body className="coverage-body">{coverage.analyst_notes}</Body>
          </Card>
        </Section>
      )}

      <Section className="coverage-section">
        <SectionTitle className="coverage-section-title">Tags</SectionTitle>
        <ChipRow className="coverage-chip-row">
          {coverage.verdict && <Chip>{coverage.verdict}</Chip>}
          {coverage.source && <Chip>{coverage.source}</Chip>}
        </ChipRow>
      </Section>
    </PageContainer>
  );
}
