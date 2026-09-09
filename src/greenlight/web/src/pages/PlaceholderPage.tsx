import { Card } from '../components';
import { HelperText, PageContainer, PageTitle } from '../components/layout.tsx';

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <PageContainer className="placeholder-page">
      <PageTitle className="placeholder-page-title">{title}</PageTitle>
      <Card padding="lg" className="placeholder-page-card">
        <HelperText>Coming soon.</HelperText>
      </Card>
    </PageContainer>
  );
}
