# Design System — MSP-BC Open Atlas

## Product Context
- **What this is:** Privacy-safe geospatial visualization of physician billing data in British Columbia
- **Who it's for:** Journalists, researchers, policy analysts investigating healthcare payment patterns
- **Space/industry:** Civic tech, data journalism, public accountability
- **Project type:** Web app (interactive map + data dashboard)

## Aesthetic Direction
- **Direction:** Editorial/Magazine
- **Decoration level:** Minimal — typography, whitespace, and the map do the talking
- **Mood:** Credible and institutional, like a well-funded ProPublica investigation. Serious about the data without being boring. The product has a point of view.
- **Reference sites:** ProPublica (propublica.org), The Markup (themarkup.org), Information is Beautiful

## Typography
- **Display/Hero:** Instrument Serif — warm editorial serif, credible without being stuffy. Free on Google Fonts. Used for app title, section headings, and chart titles.
- **Body:** Source Sans 3 — readable at small sizes, professional, pairs perfectly with serifs. All body text, filter labels, UI elements.
- **UI/Labels:** Source Sans 3 600 weight, uppercase with 0.04em letter-spacing
- **Data/Tables:** Source Sans 3 with `font-variant-numeric: tabular-nums` — keeps columns aligned without a second font
- **Code:** JetBrains Mono
- **Loading:** Google Fonts CDN
  ```html
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Source+Sans+3:ital,wght@0,300;0,400;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  ```
- **Scale:**
  - Display: 3rem (48px)
  - H1: 2rem (32px)
  - H2: 1.75rem (28px)
  - H3: 1.15rem (18.4px)
  - Body: 1rem (16px)
  - Small/UI: 0.85rem (13.6px)
  - Caption: 0.75rem (12px)

## Color
- **Approach:** Restrained — one accent + neutrals. Color is rare and meaningful.
- **Primary accent:** #C4122F — institutional red. Says "we're investigators, not administrators." Every civic data tool uses blue. This doesn't.
- **Accent hover:** #A00F27
- **Neutrals (warm):**
  - Background: #FAFAF8
  - Surface: #FFFFFF
  - Border: #E5E5E0
  - Border strong: #D1D1CC
  - Text: #1A1A1A
  - Text muted: #6B7280
  - Text light: #9CA3AF
- **Semantic:** success #1B7340, warning #B45309, error #C4122F, info #2563EB
- **Semantic backgrounds:** success-bg #F0FDF4, warning-bg #FFFBEB, error-bg #FEF2F2, info-bg #EFF6FF
- **Header/Footer:** #1A1A1A (near-black)
- **Data visualization palette (sequential, warm):**
  - #FDE8E8, #F5A3A3, #E86060, #C4122F, #8B0D21, #5C0816
- **Dark mode:** Reduce saturation 10-20%, invert surfaces (#111111 bg, #1A1A1A surface), accent shifts to #E8384F for better contrast

## Spacing
- **Base unit:** 4px
- **Density:** Comfortable — data tools need information density without feeling cramped
- **Scale:** 2xs(2px) xs(4px) sm(8px) md(16px) lg(24px) xl(32px) 2xl(48px) 3xl(64px)

## Layout
- **Approach:** Hybrid — grid-disciplined for the app (sidebar + map + charts), editorial breaks for headers and about content
- **Grid:** Sidebar 260-300px fixed, main content fluid
- **Max content width:** 1200px (for non-map pages)
- **Border radius:** 0px everywhere. Sharp edges. No rounded corners. This is precise data, not a toy.

## Motion
- **Approach:** Minimal-functional — only transitions that aid comprehension
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(50-100ms) short(150-250ms) medium(250-400ms)
- **What gets motion:** Filter changes, panel open/close, hover states, map transitions
- **What doesn't:** No scroll animations, no entrance effects, no decorative motion

## CSS Custom Properties
```css
:root {
  --accent: #C4122F;
  --accent-hover: #A00F27;
  --bg: #FAFAF8;
  --surface: #FFFFFF;
  --text: #1A1A1A;
  --text-muted: #6B7280;
  --text-light: #9CA3AF;
  --border: #E5E5E0;
  --border-strong: #D1D1CC;
  --success: #1B7340;
  --warning: #B45309;
  --error: #C4122F;
  --info: #2563EB;
  --header-bg: #1A1A1A;
  --font-display: 'Instrument Serif', Georgia, serif;
  --font-body: 'Source Sans 3', 'Source Sans Pro', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --data-1: #FDE8E8;
  --data-2: #F5A3A3;
  --data-3: #E86060;
  --data-4: #C4122F;
  --data-5: #8B0D21;
  --data-6: #5C0816;
}
```

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-29 | Initial design system created | Created by /design-consultation based on competitive research of ProPublica, The Markup, and civic data visualization sites |
| 2026-03-29 | Chose institutional red (#C4122F) over blue | Differentiation — every civic tool uses blue. Red signals investigative intent. |
| 2026-03-29 | Zero border-radius policy | Sharp edges reinforce precision and editorial credibility. Distinct from rounded SaaS aesthetic. |
| 2026-03-29 | Instrument Serif + Source Sans 3 | Editorial serif for credibility (like ProPublica's Tiempos), professional sans for readability. Both free on Google Fonts. |
