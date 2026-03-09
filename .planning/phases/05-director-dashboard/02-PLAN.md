---
id: "05-02"
title: "Director Dashboard: CSV export + per-driver history"
phase: 5
wave: 2
goal: "Implement CSV export (DIR-03) and per-driver expense history (DIR-05)"
autonomous: true
depends_on: ["05-01"]
files_modified:
  - src/web/director.py
  - src/web/templates/director_driver.html
---

# Plan 05-02: Director Dashboard — CSV Export + Driver History

## Tasks

1. `GET /panel/director/export` → StreamingResponse CSV (filtered by truck/driver/period)
2. `GET /panel/director/drivers` → driver picker page
3. `GET /panel/director/drivers/{driver_id}` → director_driver.html (all expenses for one driver)
4. Create 2 templates: director_driver.html, add export link to director_summary.html

## Acceptance Criteria
- CSV download opens in Excel without errors (UTF-8-BOM encoding)
- Driver history shows all expenses across all trips for that driver with KZT totals
- Driver picker shows list of active drivers to click through
