import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import styled from '@emotion/styled';
import { Card } from '../components';
import { CreateModal, type CreateFormData } from '../components/CreateModal';
import { ScriptCardView } from '../components/ScriptCardView';
import { UploadZoneView } from '../components/UploadZoneView';
import { Button, PageContainer, PageTitle, SectionTitle } from '../components/layout.tsx';
import { useProjectStore } from '../lib/store-project';
import type { ScriptUploadResult } from '../lib/types';

const ScriptGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  margin-top: 24px;
`;

const StatusMessage = styled.div<{ type: 'info' | 'error' | 'success' }>`
  padding: 12px 16px;
  border-radius: var(--radius);
  margin-top: 16px;
  font-size: 13px;
  background: ${({ type }) =>
    type === 'error' ? 'rgba(239, 68, 68, 0.15)' :
    type === 'success' ? 'rgba(34, 197, 94, 0.15)' :
    'rgba(50, 205, 50, 0.15)'};
  color: ${({ type }) =>
    type === 'error' ? 'var(--danger)' :
    type === 'success' ? 'var(--success)' :
    'var(--accent)'};
`;

const CtaRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const CtaTextWrap = styled.div``;

const CtaTitle = styled.div`
  font-weight: 600;
  font-size: 15px;
`;

const CtaSubtitle = styled.div`
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
`;

const EmptyMessage = styled.p`
  color: var(--text-secondary);
  margin: 0;
`;

const CtaCard = styled(Card)`
  margin-top: 16px;
`;

const ScriptsHeading = styled(SectionTitle)`
  margin-top: 24px;
`;

const IngestNotice = styled.div`
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  background: rgba(50, 205, 50, 0.12);
  color: var(--text-primary);
`;

const IngestNoticeList = styled.ul`
  margin: 6px 0 10px;
  padding-left: 18px;
  color: var(--text-secondary);
`;

const ReformatMsg = styled.div`
  margin-top: 8px;
  color: var(--text-secondary);
`;

export function WorkspacePage() {
  const scripts = useProjectStore((s) => s.scripts);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<{ type: 'info' | 'error' | 'success'; msg: string } | null>(null);
  const [runningCoverage, setRunningCoverage] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [lastUpload, setLastUpload] = useState<ScriptUploadResult | null>(null);
  const [reformatMsg, setReformatMsg] = useState<string | null>(null);
  const [reformatting, setReformatting] = useState(false);
  const navigate = useNavigate();

  const refreshSession = useProjectStore((s) => s.refreshSession);
  const loadScripts = useProjectStore((s) => s.loadScripts);
  const loadScript = useProjectStore((s) => s.loadScript);

  useEffect(() => {
    loadScripts();
  }, [loadScripts]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setStatus({ type: 'info', msg: `Uploading ${file.name}...` });

    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name.replace(/\.[^.]+$/, ''));

    try {
      const res = await fetch('/api/scripts/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Upload failed (HTTP ${res.status})`);
      }

      const data: ScriptUploadResult = await res.json();
      setLastUpload(data);
      setReformatMsg(null);
      const scenes = data.stats?.scenes ?? data.loaded?.scene_count ?? 0;
      setStatus({
        type: scenes === 0 ? 'info' : 'success',
        msg:
          scenes === 0
            ? `Uploaded: ${data.title} — no scenes detected; check the hints below`
            : `Uploaded & loaded: ${data.title} — ${scenes} scenes (${data.source_format}${data.normalized ? ' → formatted to Fountain' : ''})`,
      });
      await Promise.all([refreshSession(), loadScripts()]);
    } catch (err) {
      setLastUpload(null);
      setStatus({ type: 'error', msg: `Upload failed: ${err instanceof Error ? err.message : err}` });
    } finally {
      setUploading(false);
    }
  };

  const handleReFormat = async (scriptId: string) => {
    setReformatting(true);
    setReformatMsg(null);
    try {
      const res = await fetch(`/api/scripts/${scriptId}/normalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setReformatMsg(
        data.scene_count > 0
          ? `Re-formatted: ${data.scene_count} scenes detected` +
              (data.unchanged ? ' (same result as before)' : '')
          : 'Still no scene headings found — the file may not be a screenplay. Try the .fountain source.',
      );
      if (lastUpload) setLastUpload({ ...lastUpload, stats: data.stats, warnings: data.warnings });
      await Promise.all([refreshSession(), loadScripts()]);
    } catch (err) {
      setReformatMsg(`Re-format failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      setReformatting(false);
    }
  };

  const handleCreateScreenplay = async (form: CreateFormData) => {
    setStatus({ type: 'info', msg: 'Creating screenplay...' });
    try {
      const res = await fetch('/api/scripts/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: form.title.trim(),
          author: form.author.trim(),
          credit: form.credit.trim(),
          source: form.source.trim(),
          draft_date: form.draft_date.trim(),
          contact: form.contact.trim(),
          genre: form.genre.trim(),
        }),
      });

      if (!res.ok) throw new Error('Create failed');

      const data = await res.json();
      setStatus({
        type: 'success',
        msg: data.loaded
          ? `Created: ${data.title} — ready to write`
          : `Created: ${data.title}`,
      });
      await Promise.all([refreshSession(), loadScripts()]);
      setShowCreateModal(false);
    } catch (err) {
      setStatus({ type: 'error', msg: `Create failed: ${err}` });
    }
  };

  const handleDelete = async (scriptId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this screenplay?')) return;

    try {
      const res = await fetch(`/api/scripts/${scriptId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Delete failed');
      await loadScripts();
      setStatus({ type: 'success', msg: 'Screenplay deleted' });
    } catch (err) {
      setStatus({ type: 'error', msg: `Delete failed: ${err}` });
    }
  };

  const handleLoadScript = async (scriptId: string) => {
    const ok = await loadScript(scriptId);
    if (ok) {
      navigate('/screenplay');
    } else {
      setStatus({ type: 'error', msg: 'Failed to load screenplay' });
    }
  };

  const handleRunCoverage = async (scriptId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setRunningCoverage(scriptId);
    setStatus({ type: 'info', msg: 'Running reader agent coverage...' });

    try {
      const [_, textRes] = await Promise.all([
        loadScript(scriptId),
        fetch(`/api/scripts/${scriptId}/text`),
      ]);
      if (!textRes.ok) throw new Error('Script text not found');
      const scriptText = await textRes.text();

      const coverageRes = await fetch(`/api/scripts/${scriptId}/coverage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script_text: scriptText }),
      });
      if (!coverageRes.ok) throw new Error('Coverage failed');

      const coverage = await coverageRes.json();
      setStatus({
        type: 'success',
        msg:
          coverage.source === 'reader_agent'
            ? `Coverage complete: ${coverage.verdict}`
            : `LT-only coverage (LLM unavailable): ${coverage.llm_error ?? ''}`,
      });
      navigate('/coverage', { state: { coverage } });
    } catch (err) {
      setStatus({ type: 'error', msg: `Coverage failed: ${err}` });
    } finally {
      setRunningCoverage(null);
    }
  };

  return (
    <PageContainer className="workspace-page">
      <PageTitle className="workspace-page-title">Workspace</PageTitle>

      <Card padding="lg" className="workspace-upload-card">
        <UploadZoneView onUpload={handleUpload} uploading={uploading} />
      </Card>

      <CtaCard padding="lg">
        <CtaRow className="workspace-cta-row">
          <CtaTextWrap className="workspace-cta-text">
            <CtaTitle className="workspace-cta-title">Start from scratch</CtaTitle>
            <CtaSubtitle className="workspace-cta-subtitle">Create a blank screenplay with title page, then add scenes</CtaSubtitle>
          </CtaTextWrap>
          <Button onClick={() => setShowCreateModal(true)}>Start New Screenplay</Button>
        </CtaRow>
      </CtaCard>

      {status && <StatusMessage className={`workspace-status workspace-status--${status.type}`} type={status.type}>{status.msg}</StatusMessage>}

      {lastUpload && (lastUpload.warnings.length > 0 || (lastUpload.stats?.scenes ?? 0) === 0) && (
        <IngestNotice className="workspace-ingest-notice">
          <strong>Formatting review — {lastUpload.title}</strong>
          {lastUpload.warnings.length > 0 && (
            <IngestNoticeList className="workspace-ingest-notice-list">
              {lastUpload.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </IngestNoticeList>
          )}
          <Button variant="ghost" onClick={() => handleReFormat(lastUpload.id)} disabled={reformatting}>
            {reformatting ? 'Re-formatting…' : 'Re-format source'}
          </Button>
          {reformatMsg && <ReformatMsg className="workspace-reformat-msg">{reformatMsg}</ReformatMsg>}
        </IngestNotice>
      )}

      {scripts.length === 0 && !status && (
        <EmptyMessage className="workspace-empty">No screenplays yet. Upload a file or start from scratch above.</EmptyMessage>
      )}

      {scripts.length > 0 && (
        <>
          <ScriptsHeading className="workspace-scripts-heading">Scripts ({scripts.length})</ScriptsHeading>
          <ScriptGrid className="workspace-script-grid">
            {scripts.map((script) => (
              <ScriptCardView
                key={script.id}
                script={script}
                coverageRunning={runningCoverage === script.id}
                onLoad={() => handleLoadScript(script.id)}
                onCoverage={(e) => handleRunCoverage(script.id, e)}
                onDelete={(e) => handleDelete(script.id, e)}
              />
            ))}
          </ScriptGrid>
        </>
      )}

      {showCreateModal && (
        <CreateModal onClose={() => setShowCreateModal(false)} onCreate={handleCreateScreenplay} />
      )}
    </PageContainer>
  );
}
