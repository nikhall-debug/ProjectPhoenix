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

## Phoenix v0.9.3-alpha

### Reliability
- Added centralized version management.
- Restored manual Withings sync.
- Added automatic Withings token refresh.
- Added data freshness monitoring for Withings and Apple Health.
- Dashboard now distinguishes between connection status and data freshness.
- Added timestamps showing the last successful synchronization for supported integrations.

### UX
- Improved transparency around integration health.
- Reduced the risk of stale data influencing daily coaching.

## v0.9.2 — Readiness Intelligence & Narrative Coaching

### Added
- Readiness Engine
- Narrative Engine
- Coaching narrative generation
- Training opportunity assessment
- Risk assessment
- Confidence scoring

### Improved
- Decision Engine now uses Readiness instead of raw physiological rules
- Coach page redesigned around athlete-friendly coaching
- Recovery reasoning separated from decision making

### Architecture

Sensors
→ Athlete Context
→ Baseline Engine
→ Recovery Engine
→ Readiness Engine
→ Decision Engine
→ Narrative Engine
→ Coach

This release marks the transition from a health dashboard to an intelligent coaching system.

Project Phoenix v0.9

Major milestone: unified data collection.

New
- Integrated Withings API for body composition and health metrics
- Integrated Xert API for training freshness and fitness status
- Added Apple Health import via Health Auto Export
- Automatic syncing of supported services at startup
- Morning Snapshot now combines data from multiple sources
- Improved Streamlit dashboard layout and expandable sections

Improved
- Cleaner UI presentation
- Better separation between integrations, snapshot building and decision logic
- More robust data storage architecture

Foundation
Phoenix now has a unified health data lake capable of combining:
- Apple Health
- Withings
- Xert
- Lumen
- Morning Check-in

This establishes the platform for the next major milestone:
v1.0 – Baseline Intelligence & Recovery Engine.

# v0.9.0 – Automatic Apple Health Integration
Released: July 2026

## 🚀 New

### Automatic Apple Health JSON Integration
- Replaced manual Apple Health ZIP imports with automatic JSON synchronization.
- Phoenix now reads Health Auto Export JSON files directly from iCloud.
- Automatic imports occur on startup with duplicate protection.

### New Automatic Data Sources

Phoenix now automatically collects data from:

- Morning Check-in
- Withings
- Apple Health
- Xert

### Apple Health Metrics

Added automatic support for:

- Heart Rate Variability
- Resting Heart Rate
- Respiratory Rate
- Blood Oxygen
- Active Energy
- Exercise Minutes
- Step Count
- Walking Distance
- Walking Heart Rate
- Sleep Analysis
  - Total Sleep
  - Deep Sleep
  - Core Sleep
  - REM Sleep
  - Awake Time

### Architecture

Added a dedicated Apple Health JSON integration module.

The system now imports official Health Auto Export JSON files rather than reverse-engineering binary sync files.

### Foundation

This release establishes Phoenix's automatic health data pipeline and provides the data foundation for Athlete Context v2, Recovery Intelligence, and significantly smarter coaching.

# v0.9.0 – Automatic Apple Health Integration
Released: July 2026

## 🚀 New

### Automatic Apple Health Sync
- Added automatic Apple Health integration via Health Auto Export.
- Phoenix now reads synced Apple Health data directly from the AutoSync folder.
- No manual ZIP import required.

### New Apple Health Metrics
Phoenix now automatically imports:

- Heart Rate Variability (HRV)
- Resting Heart Rate
- Respiratory Rate
- Active Energy
- Exercise Minutes
- Step Count

### New Integration Module
- Added `apple_health_sync.py`
- Automatic startup synchronization
- Duplicate protection
- Automatic storage in `health_measurements`

### Morning Snapshot
- Added Apple Health sync status to the Morning Snapshot.

## Architecture

Phoenix now automatically collects data from:

- Morning Check-in
- Withings
- Apple Health
- Xert
- Coach Feedback

All data flows into a shared Athlete Context and Decision Engine.

## Improvements

- Archived the manual Apple Health ZIP import page.
- Apple Health now behaves like a native Phoenix integration.
- Continued modular integration architecture for future data sources.

## Foundation

This release completes the first generation of Phoenix's automatic health data platform and prepares the system for Athlete Context v2 and significantly richer coaching decisions.

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