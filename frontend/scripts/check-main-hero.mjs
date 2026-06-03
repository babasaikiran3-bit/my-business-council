import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');
const chat = readFileSync(new URL('../src/components/ChatInterface.jsx', import.meta.url), 'utf8');
const css = readFileSync(new URL('../src/components/ChatInterface.css', import.meta.url), 'utf8');

assert.match(
  app,
  /<Route\s+element=\{<AppLayout\s*\/>\}>\s*<Route\s+path="\/"\s+element=\{<Ask\s*\/>\}\s*\/>/s,
  'Given the product is the main hero, When / is routed, Then it renders Ask inside AppLayout.'
);

assert.doesNotMatch(
  app,
  /path="\/"\s+element=\{hasOnboarded\s*\?\s*<Navigate\s+to="\/ask"/,
  'Given / is the product surface, When routing is evaluated, Then / must not redirect onboarded users away from the hero.'
);

assert.match(
  chat,
  /HERO_STATS/,
  'Given the main page is the whole product, When the empty state renders, Then it includes product proof points.'
);

assert.match(
  chat,
  /부모 라운드테이블에 바로 물어보세요/,
  'Given users ask from the hero, When the empty state renders, Then the headline explicitly invites asking.'
);

assert.match(
  css,
  /\.hero-ask-panel/,
  'Given users ask from the hero, When CSS is loaded, Then the composer is visually framed as the hero action.'
);
