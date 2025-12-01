import { useState } from 'react';
import './CollapsibleSection.css';

export default function CollapsibleSection({ title, children, defaultOpen = true }) {
    const [isOpen, setIsOpen] = useState(defaultOpen);

    return (
        <div className={`collapsible-section ${isOpen ? 'open' : 'closed'}`}>
            <button
                className="section-header"
                onClick={() => setIsOpen(!isOpen)}
                type="button"
            >
                <span className="toggle-icon">{isOpen ? '▼' : '▶'}</span>
                <h3 className="section-title">{title}</h3>
            </button>

            {isOpen && (
                <div className="section-content">
                    {children}
                </div>
            )}
        </div>
    );
}
