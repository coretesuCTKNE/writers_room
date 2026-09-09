import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Shell } from './app/Shell';
import { ErrorBoundary } from './components/ErrorBoundary';
import { WorkspacePage } from './pages/WorkspacePage';
import { CoveragePage } from './pages/CoveragePage';
import { ScreenplayPage } from './pages/ScreenplayPage';
import { TableReadPage } from './pages/TableReadPage';
import { ClosingLoopPage } from './pages/ClosingLoopPage';
import { HistoryPage } from './pages/HistoryPage';
import { SchemaInspectorPage } from './pages/SchemaInspectorPage';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { AgentsPage } from './pages/AgentsPage';
import { StoryOpsPage } from './pages/StoryOpsPage';

export function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Shell>
          <Routes>
            <Route path="/" element={<Navigate to="/workspace" replace />} />
            <Route path="/workspace" element={<WorkspacePage />} />
            <Route path="/screenplay" element={<ScreenplayPage />} />
            <Route path="/coverage" element={<CoveragePage />} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/story-ops" element={<StoryOpsPage />} />
            <Route path="/cast" element={<PlaceholderPage title="Chemistry Sandbox" />} />
            <Route path="/table-read" element={<TableReadPage />} />
            <Route path="/closing-loop" element={<ClosingLoopPage />} />
            <Route path="/audit" element={<SchemaInspectorPage />} />
            <Route path="/history" element={<HistoryPage />} />
          </Routes>
        </Shell>
      </ErrorBoundary>
    </BrowserRouter>
  );
}
