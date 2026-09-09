import { Component, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack: string }): void {
    console.error('UI error:', error, info.componentStack);
  }

  reset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    if (error) {
      if (this.props.fallback) return this.props.fallback(error, this.reset);
      return (
        <div
          style={{
            padding: 24,
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-body, sans-serif)',
          }}
        >
          <h2 style={{ color: 'var(--danger)', marginBottom: 12 }}>Something broke.</h2>
          <pre
            style={{
              background: 'var(--bg-surface)',
              padding: 12,
              borderRadius: 'var(--radius)',
              overflow: 'auto',
              fontSize: 12,
            }}
          >
            {error.message}
          </pre>
          <button
            onClick={this.reset}
            style={{
              marginTop: 16,
              padding: '8px 16px',
              background: 'var(--accent)',
              color: 'var(--bg-base)',
              border: 'none',
              borderRadius: 'var(--radius)',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
