---
id: "04-02"
title: "Map Frontend: Leaflet map + HTMX 30s auto-refresh"
phase: 4
wave: 2
goal: "Build the Leaflet map template with truck markers and automatic 30-second refresh"
autonomous: true
depends_on: ["04-01"]
files_modified:
  - src/web/templates/map.html
---

# Plan 04-02: Map Frontend

## Goal
Create `map.html` Jinja2 template with:
- Leaflet.js map centered on Central Asia
- Truck markers: plate, driver name, last ping time
- HTMX polling every 30 seconds updating marker positions
- Graceful empty state (no trucks on active trips)

## Context
- Backend routes added in Plan 04-01
- `/panel/map/markers` returns JSON array: `[{lat, lng, driver_name, plate, updated_at}, ...]`
- HTMX 2.0.4 already loaded in base.html
- Requirements: LOC-02, LOC-03, LOC-04

## Tasks

### Task 1: Create map.html template

```html
{% extends "base.html" %}
{% block content %}
<h2>Карта парка</h2>
<div id="map" style="height: 600px;"></div>

<!-- HTMX polling trigger (every 30s) -->
<div hx-get="/panel/map/markers"
     hx-trigger="every 30s"
     hx-swap="none"
     id="map-poller"></div>

<!-- Leaflet CSS + JS from CDN -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<script>
  // Initialize Leaflet map centered on Central Asia
  const map = L.map('map').setView([48.0, 68.0], 4);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(map);

  // Render initial markers from server-side Jinja2
  let markers = {};
  const initialMarkers = {{ markers | tojson }};

  function updateMarkers(data) {
    // Remove old markers
    Object.values(markers).forEach(m => map.removeLayer(m));
    markers = {};

    data.forEach(function(truck) {
      const popup = `<b>${truck.plate}</b><br>${truck.driver_name}<br>${truck.updated_at}`;
      markers[truck.plate] = L.marker([truck.lat, truck.lng])
        .bindPopup(popup)
        .addTo(map);
    });
  }

  // Render initial
  updateMarkers(initialMarkers);

  // HTMX afterRequest: refresh markers from JSON response
  document.getElementById('map-poller').addEventListener('htmx:afterRequest', function(evt) {
    if (evt.detail.xhr.status === 200) {
      const data = JSON.parse(evt.detail.xhr.responseText);
      updateMarkers(data);
    }
  });
</script>
{% endblock %}
```

### Task 2: Format `updated_at` for display
In the panel.py markers query, format `updated_at` as human-readable (e.g., "10 мин назад" or datetime string).

Use simple approach: pass ISO string and display it as-is in popup.

## Acceptance Criteria
- `GET /panel/map` displays Leaflet map centered on Central Asia
- Active truck markers appear with plate, driver, and timestamp popup
- Empty state: map renders with no markers, no JS console errors
- HTMX polls `/panel/map/markers` every 30s and updates markers
- Page does not fully reload during HTMX update (LOC-03 met)
