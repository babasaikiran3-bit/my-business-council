import { useState } from 'react';
import './OnboardingQuestions.css';

export default function OnboardingQuestions({ onComplete }) {
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [profile, setProfile] = useState({
    gender: '',
    age_range: '',
    mood: ''
  });

  const questions = [
    {
      id: 'gender',
      question: 'How do you identify?',
      options: [
        { value: 'Male', label: 'Male' },
        { value: 'Female', label: 'Female' },
        { value: 'Other', label: 'Other' },
        { value: 'Prefer not to say', label: 'Prefer not to say' }
      ],
      type: 'dropdown'
    },
    {
      id: 'age_range',
      question: 'What\'s your age range?',
      options: [
        { value: '12-17', label: '12-17' },
        { value: '18-24', label: '18-24' },
        { value: '25-34', label: '25-34' },
        { value: '35-44', label: '35-44' },
        { value: '45-54', label: '45-54' },
        { value: '55-64', label: '55-64' },
        { value: '65+', label: '65+' }
      ],
      type: 'dropdown'
    },
    {
      id: 'mood',
      question: 'How are you feeling right now?',
      options: [
        { value: 'Happy', label: '😊 Happy', emoji: '😊' },
        { value: "I don't know", label: "🤔 I don't know", emoji: '🤔' },
        { value: 'Sad', label: '😔 Sad', emoji: '😔' }
      ],
      type: 'buttons'
    }
  ];

  const currentQ = questions[currentQuestion];

  const handleSelect = (value) => {
    const updatedProfile = {
      ...profile,
      [currentQ.id]: value
    };
    setProfile(updatedProfile);

    // Move to next question or complete
    if (currentQuestion < questions.length - 1) {
      setTimeout(() => {
        setCurrentQuestion(currentQuestion + 1);
      }, 300); // Small delay for UX
    } else {
      // All questions answered
      setTimeout(() => {
        onComplete(updatedProfile);
      }, 300);
    }
  };

  const handleBack = () => {
    if (currentQuestion > 0) {
      setCurrentQuestion(currentQuestion - 1);
    }
  };

  return (
    <div className="onboarding-questions">
      <div className="questions-container">
        {/* Progress indicator */}
        <div className="progress-bar">
          {questions.map((_, index) => (
            <div
              key={index}
              className={`progress-dot ${index <= currentQuestion ? 'active' : ''}`}
            />
          ))}
        </div>

        {/* Question */}
        <div className="question-content">
          <h2 className="question-text">{currentQ.question}</h2>

          {/* Answer options */}
          {currentQ.type === 'dropdown' && (
            <div className="options-dropdown">
              {currentQ.options.map((option) => (
                <button
                  key={option.value}
                  className={`option-button ${profile[currentQ.id] === option.value ? 'selected' : ''}`}
                  onClick={() => handleSelect(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}

          {currentQ.type === 'buttons' && (
            <div className="options-buttons">
              {currentQ.options.map((option) => (
                <button
                  key={option.value}
                  className={`mood-button ${profile[currentQ.id] === option.value ? 'selected' : ''}`}
                  onClick={() => handleSelect(option.value)}
                >
                  <span className="mood-emoji">{option.emoji}</span>
                  <span className="mood-label">{option.value}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Navigation */}
        {currentQuestion > 0 && (
          <button className="back-button" onClick={handleBack}>
            ← Back
          </button>
        )}
      </div>
    </div>
  );
}
