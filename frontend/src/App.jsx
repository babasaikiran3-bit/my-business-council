import { Routes, Route, Navigate } from 'react-router-dom';
import { useApp } from './context/AppContext';
import AppLayout from './components/AppLayout';
import Ask from './pages/Ask';
import Start from './pages/Start';
import Settings from './pages/Settings';
import Landing from './pages/Landing';
import './App.css';

function App() {
  const { hasOnboarded } = useApp();

  return (
    <Routes>
      {/* New visitors see the marketing landing; returning visitors skip to the app. */}
      <Route path="/" element={hasOnboarded ? <Navigate to="/ask" replace /> : <Landing />} />
      <Route path="/start" element={<Start />} />

      {/* Signed-in app shell (sidebar + bottom tabs). */}
      <Route element={<AppLayout />}>
        <Route path="/ask" element={<Ask />} />
        <Route path="/ask/:id" element={<Ask />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
