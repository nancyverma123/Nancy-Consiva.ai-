# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- Visitors to consiva.ai evaluating Consiva: founders, Data Protection Officers, compliance, legal and engineering teams at businesses that process Indian users' personal data.
- They arrive with concrete DPDP questions (consent, ROPA, breach timelines, data discovery, pricing) and want a trustworthy answer before signing up or talking to sales.

## Product Purpose
The Consiva AI Assistant answers questions about Consiva and DPDP compliance strictly from Consiva's approved public knowledge base (RAG over consiva.ai content), in the user's language, by text or hands-free voice. Success is a visitor getting a correct, sourced answer quickly and trusting Consiva more because of it.

## Positioning
A compliance vendor's assistant that refuses to guess: every answer is grounded in Consiva's own published material, shows its sources, and falls back to fixed, honest refusals when the knowledge base doesn't cover a question.

## Operating Context
- Placement: both a full-page assistant (sidebar history + chat) and, later, a collapsible widget on consiva.ai. The full page is built now and must be designed to compress into a widget.
- Voice mode is a hands-free "call": the user speaks, the assistant detects end of speech, answers aloud (ElevenLabs), and can be interrupted by talking.
- Languages: English, Hindi, Arabic (RTL), Spanish, French, German, Portuguese, Chinese.

## Capabilities and Constraints
- Stack: static HTML/CSS/vanilla JS frontend (`index.html`, `css/style.css`, `js/app.js`) served separately from a FastAPI backend. No build step.
- Features that must keep working: guest auth, chat with source citations, conversation history (load/delete/new), language selector, per-message Listen, hands-free voice mode (VAD, transcription, streamed TTS, barge-in).
- Answers are plain text today (markdown is not rendered).
- ElevenLabs free plan: limited credits; voice replies are short by design.

## Brand Commitments
- Name: "Consiva.ai" / Consiva; tagline "Consent · Intelligence · Automation".
- Binding reference: the consiva.ai website (user-confirmed). Its tokens: Inter (400–900) and JetBrains Mono; indigo #4F46E5 / #6366F1 / #818CF8, cyan #06B6D4, gold #F59E0B, green #10B981, red #F43F5E; light theme bg #F1F5FF, surface #FFFFFF, border rgba(79,70,229,.15); dark bg #03070F; heavy (900) tight-tracked headlines, uppercase pill section labels, 14–16px card radii; shield logo mark with indigo→cyan gradient.
- Logo files: https://consiva.ai/assets/images/logo/ (nav logo PNG has white wordmark for dark backgrounds; favicon.png).

## Evidence on Hand
- Knowledge base: `backend/data/consiva_public_rag_knowledge_base.pdf` (crawl of consiva.ai, 15 Sep 2026).
- No testimonials, customer logos or usage statistics are provided for the assistant; do not invent them.

## Product Principles
1. Trust over flourish: sources, honest fallbacks and clear states matter more than decoration.
2. Feel like part of consiva.ai: a visitor moving from the site to the assistant should not notice a seam.
3. Voice is a first-class conversation, not a dictation button.
4. Every state is designed: empty, loading, error, offline, mic blocked, quota reached.

## Accessibility & Inclusion
- Keyboard operable, visible focus, reduced-motion support for all animation (including the voice orb), RTL-safe layout for Arabic, WCAG AA contrast.
