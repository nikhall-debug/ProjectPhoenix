# Changelog

## v0.1 (5 July 2026)

Initial release.

### Added

- First Streamlit application
- SQLite database
- Daily check-in
- Local development environment
- Git repository
- README
- Roadmap

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