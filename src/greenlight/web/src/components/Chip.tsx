import styled from '@emotion/styled';

type ChipVariant = 'verdict' | 'severity' | 'status' | 'default';

interface ChipProps {
  variant?: ChipVariant;
  color?: 'success' | 'warn' | 'danger' | 'accent' | 'neutral';
  children: React.ReactNode;
  className?: string;
}

const StyledChip = styled.span<{ variant: ChipVariant; color: string }>`
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: ${({ color }) => {
    switch (color) {
      case 'success': return 'rgba(34, 197, 94, 0.15)';
      case 'warn': return 'rgba(234, 179, 8, 0.15)';
      case 'danger': return 'rgba(239, 68, 68, 0.15)';
      case 'accent': return 'rgba(50, 205, 50, 0.15)';
      default: return 'rgba(160, 160, 160, 0.15)';
    }
  }};
  color: ${({ color }) => {
    switch (color) {
      case 'success': return 'var(--success)';
      case 'warn': return 'var(--warn)';
      case 'danger': return 'var(--danger)';
      case 'accent': return 'var(--accent)';
      default: return 'var(--text-secondary)';
    }
  }};
  border: 1px solid ${({ color }) => {
    switch (color) {
      case 'success': return 'rgba(34, 197, 94, 0.3)';
      case 'warn': return 'rgba(234, 179, 8, 0.3)';
      case 'danger': return 'rgba(239, 68, 68, 0.3)';
      case 'accent': return 'rgba(50, 205, 50, 0.3)';
      default: return 'rgba(160, 160, 160, 0.3)';
    }
  }};
`;

function getVerdictColor(verdict: string): 'success' | 'warn' | 'danger' {
  if (verdict === 'RECOMMEND') return 'success';
  if (verdict === 'CONSIDER') return 'warn';
  return 'danger';
}

export function Chip({ variant = 'default', children, className }: ChipProps) {
  const text = String(children);
  const color = variant === 'verdict' ? getVerdictColor(text) : 'neutral';
  const merged = [`ui-chip`, variant !== 'default' && `ui-chip--${variant}`, className]
    .filter(Boolean)
    .join(' ');

  return (
    <StyledChip variant={variant} color={color} className={merged}>
      {children}
    </StyledChip>
  );
}
