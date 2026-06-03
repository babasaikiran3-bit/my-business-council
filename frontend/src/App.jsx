import { Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import Ask from './pages/Ask';
import Start from './pages/Start';
import Settings from './pages/Settings';
import './App.css';

function App() {
  return (
    <Routes>
      <Route path="/start" element={<Start />} />

      <Route element={<AppLayout />}>
        <Route path="/" element={<Ask />} />
        <Route path="/ask" element={<Ask />} />
        <Route path="/ask/:id" element={<Ask />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
