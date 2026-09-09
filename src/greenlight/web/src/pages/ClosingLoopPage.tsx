import { useLocation, useNavigate } from 'react-router-dom';
import styled from '@emotion/styled';
import { ClosingLoop } from '../components';
import { Button, PageContainer, PageTitle } from '../components/layout.tsx';

const FullHeight = styled.div`
  height: calc(100vh - 250px);
`;

const DEMO_TURNS = [
  { speaker: 'DETECTIVE', transcript: "Where were you last night?", prosody_tags: ['whispers'] },
  { speaker: 'SUSPECT', transcript: "I don't have to answer that.", prosody_tags: ['angry'] },
  { speaker: 'DETECTIVE', transcript: "You do. Now tell me.", prosody_tags: [] },
  { speaker: 'SUSPECT', transcript: "Fine. I was at the bar. Alone.", prosody_tags: ['tired'] },
];

interface ClosingLoopState {
  sessionId?: string;
  turns?: Array<{
    turn_no: number;
    speaker: string;
    transcript: string;
    prosody_tags?: string[];
    prosody_source?: string;
  }>;
  audioUrl?: string;
}

export function ClosingLoopPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as ClosingLoopState) || {};

  const turns = state.turns?.length
    ? state.turns.map((t) => ({
        speaker: t.speaker,
        transcript: t.transcript,
        prosody_tags: t.prosody_tags || [],
      }))
    : DEMO_TURNS;

  return (
    <PageContainer className="closing-loop-page">
      <PageTitle className="closing-loop-page-title">Closing Loop</PageTitle>
      <FullHeight className="closing-loop-page-stage">
        <ClosingLoop turns={turns} audioUrl={state.audioUrl} />
      </FullHeight>
      <Button variant="primary" onClick={() => navigate('/table-read')} style={{ marginTop: 24 }}>
        Take Me to Full Table Read →
      </Button>
    </PageContainer>
  );
}
