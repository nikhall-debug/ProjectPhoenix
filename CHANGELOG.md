# Changelog


## Vision

Project Phoenix is not intended to become another dashboard.

Its purpose is to help one person make better health decisions every day by combining objective sensor data, subjective human input, historical trends, and intelligent coaching.

The guiding principles are:

- Collect lots of data. Show only what matters.
- Explain every recommendation.
- Celebrate progress more than problems.
- Phoenix suggests. The user decides.
- Learn continuously from feedback.

# Project Phoenix Changelog

All notable changes to Project Phoenix will be documented in this file.

Project Phoenix is a personal health intelligence platform designed to combine data from multiple health sources with subjective daily input to provide personalized insights, coaching, and long-term health guidance.

---

# v0.8.6 – Xert Integration and Athlete Context
Released: July 2026

## Added

- Added Xert authentication and token storage.
- Added Xert training info fetch.
- Added Xert status storage in SQLite.
- Added one Xert snapshot per day.
- Added `athlete_context.py` as the central context layer.
- Decision Engine now uses Athlete Context.
- Coach recommendations now include Xert status, training load, and target XSS.
- Xert data is visible in Data Explorer.

## Improved

- Withings remains the source of truth for body weight.
- Xert weight is ignored.
- Raw Xert JSON is hidden from the main app page.
- Training Coach is now better prepared for future Phoenix Memory and Apple Health integrations.

## Foundation

This release establishes the Athlete Context architecture:

- Morning Check-in
- Lumen
- Withings
- Xert
- Coach feedback
- Plan overrides

are now moving toward one shared context for the Decision Engine.

# v0.8.4 – Decision Engine Foundation
Released: July 2026

## Added

### Decision Engine

- Introduced a dedicated `decision_engine.py` module.
- Replaced the previous direct coaching logic with a structured decision engine.
- Recommendations are now returned as structured decisions instead of simple text.

### Adaptive Coaching

Phoenix now adapts recommendations based on today's plans.

Supported coaching scenarios:

- Standard recommendation
- Race day
- Train harder
- 30-minute session
- Recovery only
- Flexible / custom plans

### Coaching Decisions

Recommendations now include:

- Training type
- Duration
- Intensity
- Confidence level
- Explanation ("Why?")
- Alternative suggestions
- Action plan

### Coach Behaviour Tracking

Added storage for coaching plan overrides.

Phoenix now records:

- Original recommendation
- User-selected plan
- Additional context
- Final adapted recommendation

This forms the foundation of the future Phoenix Memory system.

## Improved

- Training Coach redesigned around the Decision Engine.
- Better separation between decision logic and user interface.
- Coach recommendations are now extensible for future integrations.

## Foundation for v0.8.5

Prepared the project for Xert integration.

Future coaching will incorporate:

- Training freshness
- Training load
- Fitness signature
- Training recommendations

before generating daily coaching advice.

# v0.7.0 – Workflow Redesign
Released: July 2026

## Added

- Introduced a dedicated **Morning** page as the daily starting point.
- Added separate **Insights**, **Training Coach**, and **Trends** pages.
- Added a structured morning workflow:
  - Automatic data collection
  - Manual check-in
  - Morning Snapshot
  - Guided navigation to insights and coaching
- Improved Morning Snapshot messaging.
- Added cleaner navigation between pages.

## Improved

- Simplified the landing page to focus on daily input.
- Separated coaching, insights, and dashboards into dedicated modules.
- Refactored repeated UI components into reusable helper functions.
- Moved Withings synchronization into its own module.
- Improved project structure and maintainability.

## Architecture

New modules:

- `sync.py`
- `ui_helpers.py`

Pages:

- Morning
- Insights
- Training Coach
- Trends
- Data Explorer

## Foundation for v0.8

The new page architecture prepares Phoenix for an interactive coaching experience where recommendations can adapt based on:

- User feedback
- Planned training
- Race days
- Available time
- Long-term learning

---

# v0.6.5 – Refactor & Polish

## Added

- Explainable insights with **Why?**
- Evidence supporting recommendations.
- Coach feedback (Agree / Disagree + comments).
- Achievements system.

## Improved

- Cleaner project architecture.
- Reusable UI rendering.
- More robust Withings synchronization.

---

# v0.5.0 – Morning Snapshot

## Added

- Morning Snapshot.
- Automatic detection of completed daily check-ins.
- Manual Lumen integration.
- Improved dashboard layout.
- Automatic Withings synchronization.

---

# v0.4.0

## Added

- Withings OAuth integration.
- Automatic import of body measurements.
- Duplicate protection.
- Local token storage.

---

# v0.3.0

## Added

- Health measurement database.
- Analytics module.
- Dashboard metrics.
- Weight, body fat, muscle mass and blood pressure support.

---

# v0.2.0

## Added

- SQLite database.
- Daily check-in storage.
- Initial coaching logic.

---

# v0.1.0

Initial prototype.

Features:

- Manual morning check-in.
- Basic recovery recommendation.
- Project structure established.