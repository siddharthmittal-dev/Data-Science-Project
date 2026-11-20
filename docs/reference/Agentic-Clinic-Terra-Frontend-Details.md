# Agentic Clinic — Terra Frontend Download and Setup Guide

## What this download contains

Terra is the selected frontend design for the Agentic Clinic academic prototype. This ZIP contains an interactive, standalone browser mockup with fictional data. It is the **existing HTML, CSS and JavaScript prototype**, not a React/Next.js project or the complete production application.

- `index.html` — application entry point.
- `styles.css` — Terra layout, colors, typography, responsive styles and the shared style rules retained from the design study.
- `app.js` — interface rendering, sample data and simulated client-side interactions. Some shared code from the three-design study remains, but the delivered interface selects Terra.
- `README.md` — this guide.

## Download and open

1. Download `Agentic-Clinic-Terra-Frontend.zip` and extract it to a folder on your computer.
2. Open the extracted folder and double-click `index.html`, or drag it into a modern browser.
3. Allow JavaScript if it is disabled. The app runs locally without installing packages or creating an account.
4. Optional: if your browser restricts local files, serve the extracted folder from a local development web server. With Python installed, open a terminal in that folder and run `python -m http.server 8000`, then open `http://localhost:8000`.
5. For offline use, the app has fallback fonts. It attempts to download DM Sans and Manrope from Google Fonts when internet access is available; the main Terra headings also use Georgia.

No developer dependencies or package installation are required to open this mockup. The browser must support modern JavaScript, CSS and the HTML dialog element.

## Pages and interactions

- **Overview:** the Terra welcome screen, care illustration, upcoming visit, assistant entry point and recent activity.
- **Appointments:** view fictional upcoming, past and cancelled appointments; simulate booking, rescheduling and cancellation.
- **Find a doctor:** search fictional doctors by name or specialty and select a sample time.
- **Care assistant:** use scripted replies for appointment coordination and clinic-guide information; visit changes require a review and confirmation in the mockup.
- **Documents:** read fictional guides and view a simulated processing/loading state.
- **Insights:** view a fixed synthetic clinic analytics snapshot and download its weekly data as CSV.
- **Preferences:** view fictional profile details, toggle a demo reminder setting, inspect session activity and reset sample data.

Use **Ctrl+K** on Windows or **Command+K** on macOS to open page search. Escape closes a dialog. The responsive layout, keyboard focus styling and reduced-motion preference are included in the design, although a full accessibility audit has not been completed.

## What is simulated

All doctors, patients, appointments, dates, documents and metrics are synthetic. Bookings and other changes are held in browser memory for the current page session; refreshing the page resets them. The analytics snapshot is separate from the appointments changed in the mockup. No actual appointment, notification or medical service is created.

The assistant uses scripted responses. Document processing is a visual simulation; it does not upload or process a real file. The Insights page does **not yet run Chronos-Bolt**. There is no connected API, database, OAuth login, role-based access control, file storage, RAG pipeline or real reminder service. The mockup is not intended for diagnosis, prescribing or emergency care.

The hard-coded appointment dates represent a fixed sample from October–November 2026; they may be in the past when viewed later. They are demonstration values, not real availability.

## Technology and structure

- Browser frontend: plain HTML, CSS and JavaScript.
- Navigation: hash routes such as `#terra/overview`, `#terra/doctors` and `#terra/appointments`.
- Visual system: warm paper background, terracotta accent, serif headings and top navigation.
- Data: fictional JavaScript objects in `app.js`; no backend persistence.
- Artwork: inline SVG illustration. Icons are inline SVG paths.
- Fonts: externally requested Google Fonts with fallbacks; no API key is required.

For the planned full application, the approved development plan proposes a separate React/Next.js frontend, FastAPI backend, PostgreSQL, Oracle Cloud deployment and Chronos-Bolt Small forecasting. None of those integrations is included in this ZIP. The source mockup is a visual and interaction reference for that future implementation.

## Editing

Open the extracted folder in your preferred editor. Change `styles.css` for visual styling, `app.js` for sample content and behavior, or `index.html` for the document shell. Keep all three files together. Reload the browser to see saved changes. Avoid entering real patient data into this prototype.

## Deployment and safety

The files can be served by any static web server. Publishing them does not create a secure clinic application. Real deployment requires a backend, authenticated sessions, server-side permissions, secure storage, request validation, transactional booking, audit logging and a separate security review.

The package is not connected to Oracle Cloud. Oracle Cloud resources, account eligibility, free-tier limits, DNS and HTTPS remain separate setup tasks in the development plan.

## Verification

The prior shared mockup passed 36 JavaScript logic checks covering page rendering, confirmation, duplicate slots, repeated submissions, rescheduling, cancellation and undo, input escaping, citations, filtering and totals. This Terra-only package was additionally checked for JavaScript syntax and its Terra routing. These checks do not replace visual browser, accessibility, security or end-to-end backend tests.
