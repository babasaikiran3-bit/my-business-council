import React, { useState } from 'react';
import './Election.css';

function Election({ status, results, onStartElection, onProceed }) {
    const [isStarting, setIsStarting] = useState(false);

    const handleStart = () => {
        setIsStarting(true);
        onStartElection();
    };

    if (status === 'pending') {
        return (
            <div className="election-container">
                <div className="election-card">
                    <h2>Council Election Required</h2>
                    <p>Before the council can convene, a Chairman must be elected.</p>
                    <p>The models will present their manifestos and vote for a leader.</p>
                    <button
                        className="election-button"
                        onClick={handleStart}
                        disabled={isStarting}
                    >
                        {isStarting ? 'Starting Election...' : 'Commence Election'}
                    </button>
                </div>
            </div>
        );
    }

    if (status === 'running') {
        return (
            <div className="election-container">
                <div className="election-card">
                    <h2>Election in Progress...</h2>
                    <div className="loading-spinner"></div>
                    <p>Candidates are presenting manifestos and casting votes.</p>
                </div>
            </div>
        );
    }

    if (status === 'completed' && results) {
        return (
            <div className="election-container">
                <div className="election-results">
                    <div className="winner-banner">
                        <h2>Election Complete</h2>
                        <div className="winner-announcement">
                            <span className="trophy">🏆</span>
                            <h3>New Chairman Elected:</h3>
                            <div className="winner-name">{results.winner}</div>
                        </div>
                    </div>

                    <div className="election-details">
                        <div className="manifestos-section">
                            <h3>Candidate Manifestos</h3>
                            <div className="manifestos-grid">
                                {results.manifestos.map((m, i) => (
                                    <div key={i} className={`manifesto-card ${m.model === results.winner ? 'winner-card' : ''}`}>
                                        <h4>{m.model}</h4>
                                        <p>"{m.manifesto}"</p>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="votes-section">
                            <h3>Voting Record</h3>
                            <div className="votes-list">
                                {results.votes.map((v, i) => (
                                    <div key={i} className="vote-item">
                                        <span className="voter">{v.voter}</span>
                                        <span className="arrow">➜</span>
                                        <span className="voted-for">{v.vote_for}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="continue-section">
                        <p>The Council is now ready to serve.</p>
                        <button className="proceed-button" onClick={onProceed}>
                            Proceed to Council ➜
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return null;
}

export default Election;
