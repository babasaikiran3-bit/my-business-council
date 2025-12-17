import { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { AuthGuard } from './components/AuthGuard';
import { Callback } from './components/Callback';
import ErrorBoundary from './components/ErrorBoundary';
import { DashboardLayout } from './components/dashboard';
import { CopilotFeature, HomeFeature, PlaceholderFeature } from './components/features';

function App() {
  return (
    <Routes>
      {/* OAuth callback route - must be outside AuthGuard */}
      <Route path="/callback" element={<Callback />} />

      {/* All other routes require authentication */}
      <Route path="/*" element={
        <AuthGuard>
          <AuthenticatedApp />
        </AuthGuard>
      } />
    </Routes>
  );
}

/**
 * AuthenticatedApp - Main dashboard application after authentication.
 * Manages feature-based navigation within the dashboard layout.
 */
function AuthenticatedApp() {
  const [activeFeature, setActiveFeature] = useState('home');

  const handleFeatureChange = (featureId) => {
    setActiveFeature(featureId);
  };

  const renderFeature = () => {
    switch (activeFeature) {
      case 'home':
        return <HomeFeature onNavigate={handleFeatureChange} />;
      case 'copilot':
        return <CopilotFeature />;
      case 'analytics':
        return <PlaceholderFeature title="Analytics" description="Monitor AI usage and performance metrics." />;
      case 'reports':
        return <PlaceholderFeature title="Reports" description="Generate and export operational reports." />;
      case 'workflows':
        return <PlaceholderFeature title="Workflows" description="Create and manage automated AI workflows." />;
      case 'team':
        return <PlaceholderFeature title="Team Management" description="Manage team members and permissions." />;
      case 'security':
        return <PlaceholderFeature title="Security" description="Configure security settings and audit logs." />;
      case 'settings':
        return <PlaceholderFeature title="Settings" description="Configure application settings and preferences." />;
      default:
        return <HomeFeature onNavigate={handleFeatureChange} />;
    }
  };

  return (
    <ErrorBoundary>
      <DashboardLayout
        activeFeature={activeFeature}
        onFeatureChange={handleFeatureChange}
      >
        {renderFeature()}
      </DashboardLayout>
    </ErrorBoundary>
  );
}

export default App;
