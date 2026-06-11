# Frontend and Demo Application Analysis

The user-facing ecosystem of the project is split into two distinct applications: 
1. **The BharatShield Frontend (`/frontend`)**: The official portal for citizens, journalists, and authorities to submit and review deepfake reports.
2. **VibeStream Demo (`/vibestream-demo`)**: A mock social media platform used to demonstrate the real-time legal takedown capabilities of BharatShield.

---

## 1. BharatShield Frontend (`/frontend`)

The main portal is built using **Next.js (App Router)** and **TailwindCSS**, utilizing Radix UI primitives (`shadcn/ui`) for consistent component design.

### Architectural Overview
- **Routing**: Employs Next.js `app/page.tsx` as the main SPA-like controller that conditionally renders different "screens" (e.g., landing, upload, analysis, dashboard) based on React state. This avoids hard page reloads and maintains session context smoothly.
- **Role-Based Workflows**: The entire application experience pivots on the authenticated user's role (Citizen, Journalist, Police, or Authority). This is managed via `LoginPage` and passed down as props to the rendering components.
- **API Integration**: The `src/api.ts` file abstracts all Axios calls to the FastAPI backend (e.g., `/api/reports/submit`, `/api/reports/{id}/generate-legal-docs`).

### Key Components (`/frontend/components`)
- **`landing-page.tsx`**: The main entry point. Displays role-specific options. For example, Authorities see a button to access the "Authority Dashboard", while Citizens see a "Submit Media" button.
- **`upload-screen.tsx`**: Provides UI for drag-and-drop file uploads or submitting a URL. It directly hits the backend `/analyze` endpoint to run the ML inference.
- **`video-analysis-result.tsx` & `analysis-result.tsx`**: Highly detailed visual data dashboards that display the output of the ML engine. They render confidence gauges, frame-by-frame timelines (for videos), spatial heatmaps (GradCAM), and frequency-domain anomalies to explain *why* the media is fake.
- **`role-based-output.tsx`**: This is the critical nexus for action. 
  - **Citizens/Journalists** use this to submit their findings to the authority ledger.
  - **Police/Authorities** use this to view the cryptographic hash, examine the custody ledger, generate PDF affidavits via the legal engine, and push takedown notices.
- **`authority-dashboard.tsx`**: A specialized view for administrators to list all cases, review them, and manually execute takedowns.
- **`login-page.tsx`**: Simulates login and generates JWT tokens against the backend `/verify-login` endpoint.

---

## 2. VibeStream Demo (`/vibestream-demo`)

VibeStream is a mock platform replicating the UX of a modern social media app (like X/Twitter). It exists to prove that BharatShield's generated legal notices can autonomously interface with a 3rd party platform to remove illegal content.

### Architectural Overview
- Built with **React** (via Vite/CRA) and React Router (`react-router-dom`).
- It has its own lightweight backend running on an Express server (typically port 4001).

### Key Files & Workflows
- **`src/App.jsx`**: Defines standard social media routes (`/`, `/post/:id`, `/login`, `/admin`, `/user/:handle`).
- **`src/pages/Home.jsx` & `src/pages/Post.jsx`**: Render the social feed. Users can "post" text with images or videos. Crucially, each post contains a "Report to BharatShield" button. Clicking this redirects the user to the BharatShield frontend, passing the post's media URL as a query parameter.
- **`src/pages/Admin.jsx`**: The VibeStream Trust & Safety Admin Panel. 
  - When the BharatShield backend executes a takedown (`/send-takedown`), it POSTs to VibeStream's Express API (`/api/takedown`).
  - This React component polls that API (`/api/takedown-notices`) and displays incoming legal directives.
  - The VibeStream admin can then click a "Take Down Post" button, which matches the reported URL to the internal database, deletes the post, and acknowledges compliance back to the authority.
- **`server.js` (Root)**: The Express server that manages the mock database (often just in-memory or a JSON file) and receives the webhooks from the BharatShield backend.

## Summary
The dual-app architecture effectively demonstrates the complete lifecycle of a deepfake incident:
1. Discovery on a social platform (VibeStream).
2. Triage and forensic analysis on the compliance portal (BharatShield).
3. Legal packet generation and algorithmic takedown issuance.
4. Automated enforcement and removal on the origin platform (VibeStream Admin).
