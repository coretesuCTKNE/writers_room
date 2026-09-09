import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import styled from '@emotion/styled';
import WaveSurfer from 'wavesurfer.js';
import { Card, EmptyScreenplayState } from '../components';
import { Button, ErrorText, PageContainer, PageTitle, SectionTitle } from '../components/layout.tsx';
import { useProjectStore } from '../lib/store-project';
import { parseFountainCharacters, NARRATOR } from '../lib/fountainCharacters';

const TitleSuffix = styled.span`
  font-size: 13px;
  font-weight: 400;
  color: var(--accent);
  margin-left: 12px;
`;

const SceneHeader = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
`;

const SceneLabel = styled.span`
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-secondary);
`;

const RecentMarker = styled.span`
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
`;

const VersionLabel = styled.span`
  font-size: 11px;
  color: var(--text-secondary);
  margin-left: auto;
`;

const UserRoleNote = styled.div`
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
`;

const TrackNote = styled.strong`
  color: var(--accent);
`;

const StaleNote = styled.span`
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
`;

const Controls = styled.div`
  display: flex;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
`;

const SceneSelect = styled.select`
  padding: 8px 10px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  font-size: 13px;
  max-width: 420px;
`;

const Textarea = styled.textarea`
  width: 100%;
  min-height: 200px;
  padding: 12px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  font-family: var(--font-mono);
  font-size: 13px;
  resize: vertical;

  &:focus {
    outline: none;
    border-color: var(--accent);
  }
`;

const WaveformContainer = styled.div`
  margin: 24px 0;
  padding: 16px;
  background: var(--bg-elevated);
  border-radius: var(--radius);
`;

const TrackLabel = styled.div`
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  flex-wrap: wrap;
`;

const CastGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
`;

const CastCard = styled.div<{ isUser?: boolean }>`
  padding: 16px;
  background: ${({ isUser }) => (isUser ? 'rgba(50, 205, 50, 0.1)' : 'var(--bg-surface)')};
  border: 1px solid ${({ isUser }) => (isUser ? 'var(--accent)' : 'var(--bg-elevated)')};
  border-radius: var(--radius);
`;

const CharacterName = styled.div`
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 4px;
`;

const VoiceSelect = styled.select`
  width: 100%;
  padding: 8px;
  margin-top: 8px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  font-size: 13px;
`;

const UserRadio = styled.label`
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
`;

const TurnList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 24px;
`;

const TurnItem = styled.div<{ isUserCharacter?: boolean }>`
  padding: 12px;
  background: ${({ isUserCharacter }) =>
    isUserCharacter ? 'rgba(50, 205, 50, 0.1)' : 'var(--bg-elevated)'};
  border-left: 3px solid ${({ isUserCharacter }) =>
    isUserCharacter ? 'var(--accent)' : 'var(--bg-surface)'};
  border-radius: 0 var(--radius) var(--radius) 0;
  font-family: var(--font-display);
  font-size: 14px;
`;

const Speaker = styled.div`
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 4px;
  font-size: 12px;
  text-transform: uppercase;
`;

interface Voice {
  key: string;
  id: string;
  style: string;
  gender: string;
}

interface TurnResult {
  speaker: string;
  text: string;
  duration_ms: number;
  audio_url: string | null;
}

interface GenerateResult {
  characters: string[];
  turns: TurnResult[];
  reference_audio: string;
  backing_audio: string | null;
  scene_number?: number;
  user_character?: string | null;
  narration?: boolean;
  voice_preferences?: Record<string, string>;
}

const SAMPLE_SCENE = `INT. FARMHOUSE - LIVING ROOM - NIGHT

JOHNNY
(grinning)
They're coming to get you, Barbara.

BARBARA
Stop it, Johnny. This isn't funny.

Johnny peers out the window at the dark field beyond.

JOHNNY
Look. There's one of them now.

BARBARA
(panicked)
What is that? Is that... a person?`;

interface SceneInfo {
  num: number;
  heading: string;
  text: string;
}

export function TableReadPage() {
  const session = useProjectStore((s) => s.session);
  const refreshSession = useProjectStore((s) => s.refreshSession);
  const lastEditedScene = useProjectStore((s) => s.lastEditedScene);
  const [sceneText, setSceneText] = useState(SAMPLE_SCENE);
  const [scenes, setScenes] = useState<SceneInfo[]>([]);
  const [selectedNum, setSelectedNum] = useState<number | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [castMap, setCastMap] = useState<Record<string, string>>({});
  const [userCharacter, setUserCharacter] = useState<string | null>(null);
  const [narration, setNarration] = useState(false);
  const [trackUrl, setTrackUrl] = useState<string | null>(null);
  const [waveReady, setWaveReady] = useState(false);
  const [takeStale, setTakeStale] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const waveformRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);

  const sceneTextRef = useRef(sceneText);
  sceneTextRef.current = sceneText;

  useEffect(() => {
    fetch('/api/voices')
      .then((r) => r.json())
      .then(setVoices)
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const loadActiveScenes = useCallback(async () => {
    if (!session?.loaded || !session.versionId) return;
    try {
      const res = await fetch(`/api/versions/${session.versionId}`);
      if (!res.ok) return;
      const data = await res.json();
      const sceneInfos: SceneInfo[] = data.scenes ?? [];
      setScenes(sceneInfos);
      if (sceneInfos.length > 0) {
        const target =
          lastEditedScene !== null && sceneInfos.some((s) => s.num === lastEditedScene)
            ? lastEditedScene
            : sceneInfos[0].num;
        setSelectedNum(target);
        setSceneText(sceneInfos.find((s) => s.num === target)?.text ?? SAMPLE_SCENE);
      }
    } catch {
      /* keep sample scene */
    }
  }, [session?.loaded, session?.versionId, lastEditedScene]);

  const selectScene = (num: number) => {
    setSelectedNum(num);
    const sc = scenes.find((s) => s.num === num);
    if (sc) setSceneText(sc.text);
  };

  const refresh = async () => {
    await refreshSession();
  };

  useEffect(() => {
    loadActiveScenes();
  }, [loadActiveScenes]);

  const activeScriptId = useMemo(
    () => (session?.loaded ? session.scriptId : 'test_script'),
    [session],
  );

  const sceneCharacters = useMemo(
    () => parseFountainCharacters(sceneText, narration),
    [sceneText, narration],
  );

  // Prefill voice picks saved on the backend for this script
  useEffect(() => {
    let cancelled = false;
    fetch(`/api/table-read/voice-casting?script_id=${encodeURIComponent(activeScriptId)}`)
      .then((r) => (r.ok ? r.json() : {}))
      .then((saved: Record<string, string>) => {
        if (cancelled || !saved) return;
        setCastMap((prev) => ({ ...saved, ...prev }));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeScriptId]);

  // Restore the last generated take when switching scenes (audio survives navigation)
  useEffect(() => {
    if (!session?.loaded || selectedNum === null) return;
    let cancelled = false;
    fetch('/api/table-read/lookup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        script_id: activeScriptId,
        scene_number: selectedNum,
        scene_text: sceneTextRef.current,
      }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { found: boolean; stale: boolean; result: GenerateResult | null } | null) => {
        if (cancelled) return;
        if (data?.found && data.result) {
          setResult(data.result);
          setTakeStale(data.stale);
          setTrackUrl(data.result.backing_audio ?? data.result.reference_audio);
          if (data.result.user_character !== undefined) {
            setUserCharacter(data.result.user_character);
          }
          if (typeof data.result.narration === 'boolean') {
            setNarration(data.result.narration);
          }
          if (data.result.voice_preferences) {
            setCastMap((prev) => ({ ...data.result!.voice_preferences, ...prev }));
          }
        } else {
          setResult(null);
          setTrackUrl(null);
          setTakeStale(false);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [session?.loaded, activeScriptId, selectedNum]);

  useEffect(() => {
    if (!waveformRef.current || !trackUrl) return;
    setWaveReady(false);
    wavesurferRef.current?.destroy();
    const ws = WaveSurfer.create({
      container: waveformRef.current,
      waveColor: '#32cd32',
      progressColor: '#228b22',
      cursorColor: '#fff',
      barWidth: 2,
      barRadius: 2,
      height: 100,
    });
    ws.on('ready', () => setWaveReady(true));
    ws.on('error', (err: MediaError | Error) => {
      const detail =
        err instanceof Error
          ? err.message
          : `code ${err?.code ?? '?'} (${err?.constructor?.name ?? 'MediaError'})`;
      setError(`Audio load failed: ${detail} — URL: ${trackUrl}`);
      setWaveReady(false);
    });
    wavesurferRef.current = ws;
    ws.load(trackUrl);
    return () => {
      ws.destroy();
      if (wavesurferRef.current === ws) wavesurferRef.current = null;
    };
  }, [trackUrl]);

  const generate = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const res = await fetch('/api/table-read/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script_id: activeScriptId,
          scene_text: sceneText,
          scene_number: selectedNum ?? 0,
          voice_preferences: Object.keys(castMap).length ? castMap : undefined,
          user_character: userCharacter ?? undefined,
          narration,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data: GenerateResult = await res.json();
      setResult(data);
      setTakeStale(false);
      setTrackUrl(data.backing_audio ?? data.reference_audio);
    } catch (err) {
      setError(String(err));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <PageContainer className="table-read-page">
      <PageTitle className="table-read-page-title">
        Ghost Cast Table Read
        {session?.loaded && <TitleSuffix>{session.title}</TitleSuffix>}
      </PageTitle>

      {session?.loaded && scenes.length === 0 && (
        <EmptyScreenplayState
          message="No scenes in this screenplay yet. Add scenes to generate a table read."
          ctaLabel="Go to Workspace"
          showCta
        />
      )}

      <Card padding="lg" className="table-read-config-card">
        {scenes.length > 0 && (
          <SceneHeader className="table-read-scene-header">
            <SceneLabel className="table-read-scene-label">Scene</SceneLabel>
            <SceneSelect className="table-read-scene-select" value={selectedNum ?? ''} onChange={(e) => selectScene(Number(e.target.value))}>
              {scenes.map((s) => (
                <option key={s.num} value={s.num}>
                  {String(s.num).padStart(2, '0')} — {s.heading}
                </option>
              ))}
            </SceneSelect>
            {lastEditedScene !== null && selectedNum === lastEditedScene && (
              <RecentMarker className="table-read-recent-marker">● recently edited</RecentMarker>
            )}
            <VersionLabel className="table-read-version-label">
              {session?.branches.find((b) => b.branch_id === session.branchId)?.name}@
              {session?.versionId.slice(0, 8)}
            </VersionLabel>
            <Button variant="ghost" onClick={refresh}>↻ Sync</Button>
          </SceneHeader>
        )}
        <Textarea
          className="table-read-scene-textarea"
          value={sceneText}
          onChange={(e) => {
            setSceneText(e.target.value);
            if (result) setTakeStale(true);
          }}
          placeholder="Paste Fountain scene here..."
        />
        <Controls className="table-read-controls">
          <Button variant="primary" onClick={generate} disabled={isGenerating}>
            {isGenerating ? 'Performing...' : result ? 'Regenerate Table Read' : 'Generate Table Read'}
          </Button>
          {trackUrl && (
            <Button
              variant="ghost"
              onClick={() => {
                if (waveReady) wavesurferRef.current?.playPause();
              }}
              disabled={!waveReady}
            >
              {waveReady ? 'Play / Pause' : 'Decoding audio...'}
            </Button>
          )}
        </Controls>
      </Card>

      {error && (
        <Card padding="md" className="table-read-error-card">
          <ErrorText>{error}</ErrorText>
        </Card>
      )}

      {sceneCharacters.length > 0 && (
        <>
          <SectionTitle className="table-read-cast-title" style={{ marginTop: 32 }}>
            CAST — pick voices, mark who you play
            <Button
              variant={narration ? 'primary' : 'ghost'}
              onClick={() => setNarration((v) => !v)}
              style={{ marginLeft: 12 }}
            >
              Narrator: {narration ? 'On' : 'Off'}
            </Button>
          </SectionTitle>
          <CastGrid className="table-read-cast-grid">
            {sceneCharacters.map((character) => (
              <CastCard key={character} isUser={userCharacter === character} className="table-read-cast-card">
                <CharacterName className="table-read-character-name">{character}</CharacterName>
                {character === NARRATOR && (
                  <UserRoleNote className="table-read-user-role-note">{narration ? 'Voicing scene actions' : 'Off'}</UserRoleNote>
                )}
                {userCharacter === character && (
                  <UserRoleNote className="table-read-user-role-note">YOUR ROLE — silent on karaoke track</UserRoleNote>
                )}
                <VoiceSelect
                  className="table-read-voice-select"
                  value={castMap[character] ?? ''}
                  onChange={(e) =>
                    setCastMap((prev) => ({ ...prev, [character]: e.target.value }))
                  }
                >
                  <option value="">Auto-assign</option>
                  {voices.map((v) => (
                    <option key={v.key} value={v.key}>
                      {v.id} — {v.style}
                    </option>
                  ))}
                </VoiceSelect>
                {character !== NARRATOR && (
                  <UserRadio className="table-read-user-radio">
                    <input
                      type="radio"
                      name="user-character"
                      checked={userCharacter === character}
                      onChange={() =>
                        setUserCharacter((prev) => (prev === character ? null : character))
                      }
                    />
                    I read this role live
                  </UserRadio>
                )}
              </CastCard>
            ))}
          </CastGrid>
        </>
      )}

      {result && (
        <>
          {trackUrl && (
            <WaveformContainer className="table-read-waveform-container">
              <TrackLabel className="table-read-track-label">
                Now loaded:{' '}
                <TrackNote className="table-read-track-note">
                  {result.backing_audio === trackUrl
                    ? 'KARAOKE BACKING TRACK (your role = silence gaps)'
                    : 'REFERENCE TAKE (all roles voiced)'}
                </TrackNote>
                {takeStale && (
                  <StaleNote className="table-read-stale-note">— saved take, scene changed since. Regenerate to refresh.</StaleNote>
                )}
              </TrackLabel>
              <div ref={waveformRef} className="table-read-waveform" />
            </WaveformContainer>
          )}

          <TurnList className="table-read-turn-list">
            {result.turns.map((turn, i) => (
              <TurnItem key={i} isUserCharacter={turn.speaker === userCharacter} className="table-read-turn-item">
                <Speaker className="table-read-turn-speaker">{turn.speaker}</Speaker>
                <div className="table-read-turn-text">{turn.text}</div>
              </TurnItem>
            ))}
          </TurnList>
        </>
      )}
    </PageContainer>
  );
}
