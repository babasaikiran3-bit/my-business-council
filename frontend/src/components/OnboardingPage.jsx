import { useState, useEffect, useRef } from 'react';
import './OnboardingPage.css';

// Animated Stars Background Component
const StarField = () => {
  const canvasRef = useRef(null);
  const starsRef = useRef([]);
  const animationRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const createStar = () => {
      const angle = Math.random() * Math.PI * 2;
      const speed = 0.3 + Math.random() * 0.5;
      return {
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        size: 3 + Math.random() * 5,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 0,
        maxLife: 120 + Math.random() * 60, // 2-3 seconds at 60fps
      };
    };

    // Initialize with some stars
    for (let i = 0; i < 30; i++) {
      const star = createStar();
      star.life = Math.random() * star.maxLife; // Stagger initial life
      starsRef.current.push(star);
    }

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Spawn new stars
      if (starsRef.current.length < 50 && Math.random() < 0.15) {
        starsRef.current.push(createStar());
      }

      // Update and draw stars
      starsRef.current = starsRef.current.filter((star) => {
        star.x += star.vx;
        star.y += star.vy;
        star.life++;

        // Calculate opacity based on life (fade in, stay, fade out)
        let opacity;
        const fadeInDuration = 20;
        const fadeOutStart = star.maxLife - 40;

        if (star.life < fadeInDuration) {
          opacity = star.life / fadeInDuration;
        } else if (star.life > fadeOutStart) {
          opacity = (star.maxLife - star.life) / 40;
        } else {
          opacity = 1;
        }

        // Draw star
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 165, 0, ${opacity * 0.6})`;
        ctx.fill();
        // Keep star if still alive
        return star.life < star.maxLife;
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  return <canvas ref={canvasRef} className="onboarding-star-field" />;
};

// SVG Icons as components
const SparkleIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 16 16" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M8 0L9.5 6.5L16 8L9.5 9.5L8 16L6.5 9.5L0 8L6.5 6.5L8 0Z"/>
  </svg>
);

const ChevronIcon = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 16 16" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
  </svg>
);

const ArrowIcon = ({ style }) => (
  <svg style={style} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 5V19M12 5L6 11M12 5L18 11" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

export default function OnboardingPage({
  logoText = "yourapp",
  placeholder = "What do you want to know?",
  onSubmit,
  onSignIn,
  onSignUp,
}) {
  const [inputValue, setInputValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSubmit && inputValue.trim()) {
      onSubmit(inputValue);
    }
  };

  return (
    <div className="onboarding-container">
      {/* Animated Stars Background */}
      <StarField />

      {/* Header */}
      <header className="onboarding-header">
        <img src="/image3.svg" alt="Logo" className="onboarding-logo-small" />
        <div className="onboarding-header-buttons">
          <button className="onboarding-sign-in-btn" onClick={onSignIn}>
            Sign in
          </button>
          <button className="onboarding-sign-up-btn" onClick={onSignUp}>
            Sign up
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="onboarding-main">
        {/* Logo */}
        <div className="onboarding-logo-container">
          <img src="/image3.svg" alt={logoText} className="onboarding-logo-icon" />
          <span className="onboarding-logo-text">{logoText}</span>
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="onboarding-input-container">
          <div className={`onboarding-input-wrapper ${isFocused ? 'focused' : ''}`}>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder={placeholder}
              className="onboarding-input"
            />
            <div className="onboarding-input-actions">
              <button type="button" className="onboarding-model-selector">
                <SparkleIcon className="onboarding-sparkle-icon" />
                <span>Auto</span>
                <ChevronIcon style={{ width: 12, height: 12 }} />
              </button>
              <button type="submit" className="onboarding-submit-btn">
                <ArrowIcon style={{ width: 20, height: 20 }} />
              </button>
            </div>
          </div>
        </form>

        {/* Catchy Phrase */}
        <p className="onboarding-tagline">
          Your personal wellness companion, always here to listen and support you.
        </p>

        {/* Auth Buttons */}
        <div className="onboarding-auth-buttons">
          <button className="onboarding-pill" onClick={onSignIn}>
            Log In
          </button>
          <button className="onboarding-pill" onClick={onSignUp}>
            Sign Up
          </button>
        </div>
      </main>

      {/* Footer */}
      <footer className="onboarding-footer">
        <p className="onboarding-footer-text">
          By messaging, you agree to our{' '}
          <a href="/terms" className="onboarding-footer-link">
            Terms
          </a>
          {' '}and{' '}
          <a href="/privacy" className="onboarding-footer-link">
            Privacy Policy
          </a>
          .
        </p>
      </footer>
    </div>
  );
}
