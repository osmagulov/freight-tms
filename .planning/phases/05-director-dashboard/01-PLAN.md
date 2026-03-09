---
id: "05-01"
title: "Director Dashboard: cost summary + per-truck + anomaly history"
phase: 5
wave: 1
goal: "Implement director routes for cost summary (DIR-01), per-truck breakdown (DIR-02), and anomaly history (DIR-04)"
autonomous: true
depends_on: []
files_modified:
  - src/web/director.py
  - src/main.py
  - src/web/templates/base.html
  - src/web/templates/director_summary.html
  - src/web/templates/director_trucks.html
  - src/web/templates/director_anomalies.html
---

# Plan 05-01: Director Dashboard — Summary, Trucks, Anomalies

## Tasks

1. Create `src/web/director.py` with APIRouter prefix `/panel/director`
2. `GET /panel/director` → director_summary.html (expense totals by category + trip count for period)
3. `GET /panel/director/trucks` → director_trucks.html (per-vehicle trip-by-trip cost breakdown)
4. `GET /panel/director/anomalies` → director_anomalies.html (full anomaly log including false alarms)
5. Register router in main.py
6. Add "Директор" nav link to base.html
7. Create 3 templates

## Acceptance Criteria
- Summary shows totals by FUEL/PER_DIEM/FINE/REPAIR/OTHER for selected period
- Per-truck shows each vehicle's trips with km and KZT totals
- Anomaly history shows all anomalies with status (active/false alarm)
