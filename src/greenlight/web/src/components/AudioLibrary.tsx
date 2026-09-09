import { useEffect, useState } from 'react';
import styled from '@emotion/styled';

const Panel = styled.section`
  margin-bottom: 40px;
`;

const SectionTitle = styled.h2`
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const AssetList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const AssetRow = styled.div<{ missing?: boolean }>`
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 10px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  opacity: ${({ missing }) => (missing ? 0.5 : 1)};
`;

const PurposeChip = styled.span<{ purpose: string }>`
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  background: ${({ purpose }) =>
    purpose === 'table_read' ? 'rgba(50, 205, 50, 0.15)' :
    purpose === 'backing_track' ? 'rgba(126, 87, 194, 0.2)' :
    'var(--bg-elevated)'};
  color: ${({ purpose }) =>
    purpose === 'table_read' ? 'var(--accent)' :
    purpose === 'backing_track' ? '#b39ddb' :
    'var(--text-secondary)'};
`;

const AssetName = styled.div`
  flex: 1;
  font-family: var(--font-mono);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const AssetMeta = styled.div`
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
`;

const SmallButton = styled.button`
  padding: 5px 12px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: none;
  border-radius: var(--radius);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition);

  &:hover {
    background: var(--accent);
    color: var(--bg-base);
  }
`;

const DeleteButton = styled(SmallButton)`
  &:hover {
    background: var(--danger);
    color: white;
  }
`;

interface Asset {
  asset_id: string;
  script_id: string;
  purpose: string;
  audio_url: string;
  filename: string;
  file_exists: boolean;
  size_bytes: number;
  created_at: string;
}

function fmtSize(bytes: number): string {
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function AudioLibrary() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [playingId, setPlayingId] = useState<string | null>(null);

  const load = () => {
    fetch('/api/assets')
      .then((r) => r.json())
      .then(setAssets)
      .catch(() => {});
  };

  useEffect(load, []);

  const handleDelete = async (assetId: string) => {
    await fetch(`/api/assets/${assetId}`, { method: 'DELETE' });
    setPlayingId(null);
    load();
  };

  const togglePlay = (asset: Asset) => {
    if (playingId === asset.asset_id) {
      setPlayingId(null);
    } else {
      setPlayingId(asset.asset_id);
    }
  };

  if (assets.length === 0) {
    return (
      <Panel className="audio-library">
        <SectionTitle className="audio-library-section-title">Audio Library</SectionTitle>
        <div className="audio-library-empty" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          No audio assets yet. Generate a table read —
          it's stored here automatically.
        </div>
      </Panel>
    );
  }

  return (
    <Panel className="audio-library">
      <SectionTitle className="audio-library-section-title">Audio Library ({assets.length})</SectionTitle>
      <AssetList className="audio-library-list">
        {assets.map((asset) => (
          <AssetRow key={asset.asset_id} missing={!asset.file_exists} className="audio-library-asset">
            <PurposeChip className="audio-library-purpose" purpose={asset.purpose}>{asset.purpose}</PurposeChip>
            <AssetName className="audio-library-name" title={asset.filename}>{asset.filename}</AssetName>
            <AssetMeta className="audio-library-meta">{fmtSize(asset.size_bytes)}</AssetMeta>
            <AssetMeta className="audio-library-meta">{new Date(asset.created_at).toLocaleString()}</AssetMeta>
            {asset.file_exists && (
              <>
                <SmallButton className="audio-library-btn" onClick={() => togglePlay(asset)}>
                  {playingId === asset.asset_id ? 'Close' : 'Play'}
                </SmallButton>
                <a className="audio-library-download" href={asset.audio_url} download={asset.filename}>
                  <SmallButton className="audio-library-btn">Download</SmallButton>
                </a>
              </>
            )}
            {!asset.file_exists && <AssetMeta className="audio-library-missing">file missing</AssetMeta>}
            <DeleteButton className="audio-library-btn audio-library-btn--delete" onClick={() => handleDelete(asset.asset_id)}>Delete</DeleteButton>
          </AssetRow>
        ))}
        {playingId && (
          <audio
            autoPlay
            controls
            src={assets.find((a) => a.asset_id === playingId)?.audio_url}
            className="audio-library-player"
            style={{ width: '100%' }}
          />
        )}
      </AssetList>
    </Panel>
  );
}
