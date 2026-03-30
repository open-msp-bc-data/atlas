# MSP-BC Open Atlas — Frontend

Interactive map and data visualization for the MSP-BC Open Atlas project.

## Tech Stack

- **React 19** with Vite 8
- **Leaflet** with marker clustering and heatmap layers
- **Recharts** for bar and pie charts
- **Design system:** Instrument Serif + Source Sans 3 (see [DESIGN.md](../DESIGN.md))

## Components

| Component | Description |
|-----------|-------------|
| `App.jsx` | Main layout: header, sidebar, map, charts, footer |
| `PhysicianMap.jsx` | Leaflet map with specialty-colored marker clusters and billing heatmap |
| `FilterPanel.jsx` | Dropdowns for year, specialty, city, health authority, and heatmap toggle |
| `AggregationCharts.jsx` | Top regions bar chart and billing distribution pie chart |
| `TrendPanel.jsx` | Per-physician year-over-year billing trend (appears on marker click) |

## Development

```bash
# Install dependencies
npm install

# Start dev server (proxies API calls to localhost:8000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

The dev server proxies `/physicians`, `/aggregations`, `/trends`, `/heatmap`, and `/health` to the backend at `http://localhost:8000`. See `vite.config.js` for proxy configuration.

## Design System

All visual decisions (colors, typography, spacing, border-radius) are defined in [DESIGN.md](../DESIGN.md) and implemented via CSS custom properties in `src/App.css`.

Key tokens:
- **Accent:** `#C4122F` (institutional red)
- **Display font:** Instrument Serif (Google Fonts)
- **Body font:** Source Sans 3 (Google Fonts)
- **Border radius:** 0px everywhere (sharp edges)
- **Data palette:** Sequential red (`#FDE8E8` to `#5C0816`)

Fonts are loaded via `<link>` tags in `index.html`.
