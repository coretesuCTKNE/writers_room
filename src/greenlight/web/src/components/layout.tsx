import styled from '@emotion/styled';
import type { ButtonHTMLAttributes, HTMLAttributes } from 'react';

function cx(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(' ');
}

const StyledPageContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto;
`;

export const PageContainer = ({ children, className, ...rest }: HTMLAttributes<HTMLDivElement>) => (
  <StyledPageContainer className={cx('ui-page-container', className)} {...rest}>
    {children}
  </StyledPageContainer>
);

export const WidePageContainer = ({ children, className, ...rest }: HTMLAttributes<HTMLDivElement>) => (
  <StyledWidePageContainer className={cx('ui-page-container ui-page-container--wide', className)} {...rest}>
    {children}
  </StyledWidePageContainer>
);

export const FullHeightContainer = styled.div`
  width: 100%;
  padding: 8px;
  height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  min-height: 0;
`;

const StyledWidePageContainer = styled.div`
  width: 100%;
  padding: 0 32px;
`;

const StyledPageTitle = styled.h1`
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 20px;
  color: var(--text-primary);
`;

export const PageTitle = ({ children, className, ...rest }: HTMLAttributes<HTMLHeadingElement>) => (
  <StyledPageTitle className={cx('ui-page-title', className)} {...rest}>
    {children}
  </StyledPageTitle>
);

const StyledSectionTitle = styled.h2`
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary);
`;

export const SectionTitle = ({ children, className, ...rest }: HTMLAttributes<HTMLHeadingElement>) => (
  <StyledSectionTitle className={cx('ui-section-title', className)} {...rest}>
    {children}
  </StyledSectionTitle>
);

const StyledHelperText = styled.p`
  color: var(--text-secondary);
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.5;
`;

export const HelperText = ({ children, className, ...rest }: HTMLAttributes<HTMLParagraphElement>) => (
  <StyledHelperText className={cx('ui-helper-text', className)} {...rest}>
    {children}
  </StyledHelperText>
);

const StyledErrorText = styled.p`
  color: var(--danger);
  font-size: 12px;
  margin: 8px 0 0;
`;

export const ErrorText = ({ children, className, ...rest }: HTMLAttributes<HTMLParagraphElement>) => (
  <StyledErrorText className={cx('ui-error-text', className)} {...rest}>
    {children}
  </StyledErrorText>
);

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';

const variantStyles: Record<Variant, { bg: string; color: string; border: string }> = {
  primary: {
    bg: 'var(--accent)',
    color: 'var(--bg-base)',
    border: 'var(--accent)',
  },
  secondary: {
    bg: 'var(--bg-elevated)',
    color: 'var(--text-primary)',
    border: 'var(--bg-elevated)',
  },
  danger: {
    bg: 'var(--danger)',
    color: '#fff',
    border: 'var(--danger)',
  },
  ghost: {
    bg: 'transparent',
    color: 'var(--text-secondary)',
    border: 'transparent',
  },
};

const StyledButton = styled.button<{ variant: Variant }>`
  padding: 8px 16px;
  background: ${({ variant }) => variantStyles[variant].bg};
  color: ${({ variant }) => variantStyles[variant].color};
  border: 1px solid ${({ variant }) => variantStyles[variant].border};
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition);

  &:hover:not(:disabled) {
    opacity: 0.9;
    border-color: var(--accent);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export const Button = ({ variant = 'secondary', children, className, ...rest }: ButtonProps) => (
  <StyledButton variant={variant} className={cx(`ui-button ui-button--${variant}`, className)} {...rest}>
    {children}
  </StyledButton>
);

const StyledStack = styled.div<{ gap: number; direction: 'row' | 'column' }>`
  display: flex;
  flex-direction: ${({ direction }) => direction};
  gap: ${({ gap }) => gap}px;
`;

interface StackProps extends HTMLAttributes<HTMLDivElement> {
  gap?: number;
  direction?: 'row' | 'column';
}

export const Stack = ({ gap = 12, direction = 'column', children, className, ...rest }: StackProps) => (
  <StyledStack gap={gap} direction={direction} className={cx('ui-stack', className)} {...rest}>
    {children}
  </StyledStack>
);

export const Row = ({ gap = 12, children, className, ...rest }: StackProps) => (
  <Stack gap={gap} direction="row" className={cx('ui-row', className)} {...rest}>
    {children}
  </Stack>
);
