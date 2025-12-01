
import { useState } from 'react';
import Stage1 from './components/Stage1';
import Stage2 from './components/Stage2';
import Stage3 from './components/Stage3';
import CollapsibleSection from './components/CollapsibleSection';
import './App.css';

function App() {
  const [question, setQuestion] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // State for each stage
  const [stage1Data, setStage1Data] = useState(null);
  const [stage2Data, setStage2Data] = useState(null);
  const [stage3Data, setStage3Data] = useState(null);
  const [metadata, setMetadata] = useState(null);

  // Loading states
  const [loadingStage1, setLoadingStage1] = useState(false);
  const [loadingStage2, setLoadingStage2] = useState(false);
  const [loadingStage3, setLoadingStage3] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    // Reset all states
    setIsProcessing(true);
    setStage1Data(null);
    setStage2Data(null);
    setStage3Data(null);
    setMetadata(null);

    try {
      // --- Stage 1 ---
      setLoadingStage1(true);
      const res1 = await fetch('http://localhost:8001/api/evaluate/stage1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      if (!res1.ok) throw new Error('Stage 1 failed');
      const data1 = await res1.json();
      setStage1Data(data1.stage1);
      setLoadingStage1(false);

      // --- Stage 2 ---
      setLoadingStage2(true);
      const res2 = await fetch('http://localhost:8001/api/evaluate/stage2', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          stage1_results: data1.stage1
        }),
      });
      if (!res2.ok) throw new Error('Stage 2 failed');
      const data2 = await res2.json();
      setStage2Data(data2.stage2);
      setMetadata(data2.metadata);
      setLoadingStage2(false);

      // --- Stage 3 ---
      setLoadingStage3(true);
      const res3 = await fetch('http://localhost:8001/api/evaluate/stage3', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stage2_results: data2.stage2,
          label_to_model: data2.metadata.label_to_model
        }),
      });
      if (!res3.ok) throw new Error('Stage 3 failed');
      const data3 = await res3.json();
      setStage3Data(data3.stage3);
      setLoadingStage3(false);

    } catch (error) {
      console.error('Error:', error);
      alert('Evaluation failed. Please check console for details.');
      setLoadingStage1(false);
      setLoadingStage2(false);
      setLoadingStage3(false);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="app">
      <div className="main-content">
        <header className="app-header">
          <h1>Open Cross-Evaluation for Language Models</h1>
          <p>Anonymous peer scoring across LLMs for toxicity, bias, hallucinations, and political tilt.</p>
        </header>

        <form onSubmit={handleSubmit} className="query-form">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Enter your question here..."
            rows={4}
            disabled={isProcessing}
          />
          <button type="submit" disabled={isProcessing || !question.trim()}>
            {isProcessing ? 'Evaluating...' : 'Evaluate'}
          </button>
        </form>

        <div className="results-container">
          {/* Stage 1 Section */}
          {(loadingStage1 || stage1Data) && (
            <CollapsibleSection title="Stage 1: Individual Responses" defaultOpen={true}>
              {loadingStage1 ? (
                <div className="loading-indicator">
                  <div className="spinner"></div>
                  <p>Gathering responses from council models...</p>
                </div>
              ) : (
                <Stage1 responses={stage1Data} />
              )}
            </CollapsibleSection>
          )}

          {/* Stage 2 Section */}
          {(loadingStage2 || stage2Data) && (
            <CollapsibleSection title="Stage 2: Peer Evaluations" defaultOpen={true}>
              {loadingStage2 ? (
                <div className="loading-indicator">
                  <div className="spinner"></div>
                  <p>Models are evaluating each other...</p>
                </div>
              ) : (
                <Stage2 rankings={stage2Data} labelToModel={metadata?.label_to_model} />
              )}
            </CollapsibleSection>
          )}

          {/* Stage 3 Section */}
          {(loadingStage3 || stage3Data) && (
            <CollapsibleSection title="Stage 3: Final Scoreboard" defaultOpen={true}>
              {loadingStage3 ? (
                <div className="loading-indicator">
                  <div className="spinner"></div>
                  <p>Calculating final scores...</p>
                </div>
              ) : (
                <Stage3 finalResponse={stage3Data} />
              )}
            </CollapsibleSection>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
