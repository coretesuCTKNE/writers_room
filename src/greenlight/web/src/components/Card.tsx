import styled from '@emotion/styled';

interface CardProps {
  padding?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

const StyledCard = styled.div<{ padding: string }>`
  background: var(--bg-surface);
  border: 1px solid var(--bg-elevated);
  border-radius: var(--radius);
  padding: ${({ padding }) =>
    padding === 'sm' ? '12px' : padding === 'lg' ? '24px' : '16px'};
`;

export function Card({ padding = 'md', children, className, style }: CardProps) {
  return (
    <StyledCard
      padding={padding}
      className={[`ui-card ui-card--padding-${padding}`, className].filter(Boolean).join(' ')}
      style={style}
    >
      {children}
    </StyledCard>
  );
}
