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
  // Navigation params for features (e.g., conversationId from search)
  const [featureParams, setFeatureParams] = useState({});

  /**
   * Handle feature navigation with optional params.
   * @param {string} featureId - The feature to navigate to
   * @param {Object} params - Optional params to pass to the feature
   */
  const handleFeatureChange = (featureId, params = {}) => {
    setActiveFeature(featureId);
    setFeatureParams(params);
  };

  /**
   * Render the active feature wrapped in its own ErrorBoundary.
   * This ensures errors in one feature don't crash the entire dashboard.
   */
  const renderFeature = () => {
    // Use key prop to reset ErrorBoundary when switching features
    const boundaryKey = `feature-${activeFeature}`;

    switch (activeFeature) {
      case 'home':
        return (
          <ErrorBoundary key={boundaryKey}>
            <HomeFeature onNavigate={handleFeatureChange} />
          </ErrorBoundary>
        );
      case 'copilot':
        return (
          <ErrorBoundary key={boundaryKey}>
            <CopilotFeature initialConversationId={featureParams.conversationId} />
          </ErrorBoundary>
        );
      case 'analytics':
        return (
          <ErrorBoundary key={boundaryKey}>
            <PlaceholderFeature title="Analytics" description="Monitor AI usage and performance metrics." />
          </ErrorBoundary>
        );
      case 'reports':
        return (
          <ErrorBoundary key={boundaryKey}>
            <PlaceholderFeature title="Reports" description="Generate and export operational reports." />
          </ErrorBoundary>
        );
      case 'workflows':
        return (
          <ErrorBoundary key={boundaryKey}>
            <PlaceholderFeature title="Workflows" description="Create and manage automated AI workflows." />
          </ErrorBoundary>
        );
      case 'team':
        return (
          <ErrorBoundary key={boundaryKey}>
            <PlaceholderFeature title="Team Management" description="Manage team members and permissions." />
          </ErrorBoundary>
        );
      case 'security':
        return (
          <ErrorBoundary key={boundaryKey}>
            <PlaceholderFeature title="Security" description="Configure security settings and audit logs." />
          </ErrorBoundary>
        );
      case 'settings':
        return (
          <ErrorBoundary key={boundaryKey}>
            <PlaceholderFeature title="Settings" description="Configure application settings and preferences." />
          </ErrorBoundary>
        );
      default:
        return (
          <ErrorBoundary key={boundaryKey}>
            <HomeFeature onNavigate={handleFeatureChange} />
          </ErrorBoundary>
        );
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
