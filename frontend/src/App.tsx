import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { PageLayout } from './components/common/PageLayout';
import { DashboardPage } from './pages/DashboardPage';
import { WorkflowControlPage } from './pages/WorkflowControlPage';
import { KnowledgeExplorerPage } from './pages/KnowledgeExplorerPage';
import './App.css';

function App() {
  return (
    <Router>
      <PageLayout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/workflows" element={<WorkflowControlPage />} />
          <Route path="/explorer" element={<KnowledgeExplorerPage />} />
        </Routes>
      </PageLayout>
    </Router>
  );
}

export default App;
