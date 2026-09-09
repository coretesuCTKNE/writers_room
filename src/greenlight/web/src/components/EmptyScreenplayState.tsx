import styled from '@emotion/styled';
import { Card } from './Card';

const EmptyCard = styled(Card)`
  text-align: center;
  padding: 48px 24px;
  background: var(--bg-surface);
  border: 1px dashed var(--bg-elevated);
`;

const Icon = styled.div`
  font-size: 32px;
  margin-bottom: 16px;
  opacity: 0.4;
`;

const Title = styled.h3`
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
`;

const Description = styled.p`
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px;
  line-height: 1.5;
`;

const Cta = styled.button`
  padding: 8px 16px;
  background: var(--accent);
  color: var(--bg-base);
  border: none;
  border-radius: var(--radius);
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: all var(--transition);

  &:hover {
    background: var(--accent-dim);
  }
`;

interface EmptyScreenplayStateProps {
  message?: string;
  ctaLabel?: string;
  onCta?: () => void;
  showCta?: boolean;
}

export function EmptyScreenplayState({
  message = 'No scenes in this screenplay yet.',
  ctaLabel = 'Go to Workspace',
  onCta,
  showCta = true,
}: EmptyScreenplayStateProps) {
  return (
    <EmptyCard padding="lg" className="empty-screenplay">
      <Icon className="empty-screenplay-icon">🎬</Icon>
      <Title className="empty-screenplay-title">Screenplay is empty</Title>
      <Description className="empty-screenplay-description">{message}</Description>
      {showCta && onCta && <Cta className="empty-screenplay-cta" onClick={onCta}>{ctaLabel}</Cta>}
    </EmptyCard>
  );
}
