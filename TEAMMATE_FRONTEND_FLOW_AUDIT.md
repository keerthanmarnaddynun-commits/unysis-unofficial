# BHARATSHIELD FRONTEND FLOW AUDIT

**Generated:** June 10, 2026  
**Scope:** Complete frontend/user flow documentation  
**Branch:** keerthanmarnaddynun-commits/unysis-unofficial  
**Mode:** READ ONLY - No modifications made

---

## A. COMPLETE DEMO FLOW

### Standard User Flow (Citizen/Journalist)

1. **Login** → User selects role (Citizen/Journalist/Police/Authority) and enters identifier
2. **Landing Page** → User sees hero section with "Upload File" and "Paste URL" options
3. **Upload Screen** → User submits media (file or URL) with optional source traceability fields
4. **Processing Animation** → Evidence securing steps displayed (SHA-256 hash, timestamp, evidence lock)
5. **Analysis Result** → Multi-stream forensic analysis displayed with verdict, confidence, and fact-check
6. **Role-Based Output** → User takes action based on role:
   - Citizen: Submit grievance to I4C
   - Journalist: File grievance report
   - Police: Register official case + generate legal docs
   - Authority: Register case + navigate to authority dashboard
7. **Action Confirmation** → Success screen with tracking ID, download documents, track status
8. **Return to Landing** → User can start new analysis

### Authority/Police Flow

1. **Login** → Select Police or Authority role
2. **Landing Page** → Access to "Authority Dashboard" button (Authority only)
3. **Upload/Analyze** → Same as standard flow
4. **Role-Based Output** → Police: Register case, generate legal packet; Authority: Go to dashboard
5. **Authority Dashboard** → View all reports, filter by status, update case status, re-evaluate media, send takedown notices
6. **My Reports** → View personal report history with live tracking

---

## B. SCREEN-BY-SCREEN WORKFLOW

### 1. Entry Point: `app/page.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/app/page.tsx`

**Component:** `MainApp` (wrapped in `Home` with Suspense)

**Purpose:** Central routing controller managing all screen transitions and global state

**State Management:**
- `currentScreen`: Screen enum (landing, upload-file, upload-url, analysis, role-output, confirmation, how-it-works, authority-dashboard, metrics-dashboard, my-reports, resources)
- `userRole`: Role enum (Citizen, Journalist, Police, Authority)
- `userIdentifier`: User's ID/email/department ID
- `userName`: User's display name
- `userOrganization`: User's organization
- `accessToken`: JWT token for API auth
- `uploadedFile`: File object for analysis
- `initialUrl`: URL from query params for external sharing
- `analysisData`: Full analysis response from backend
- `submittedReportInfo`: Report submission result

**Navigation Logic:**
- If no `userRole` → Show `LoginPage`
- If `userRole` exists → Route based on `currentScreen` state
- URL query param `sourceUrl` auto-routes to upload-url screen

**Screen Transitions:**
- `landing` → `upload-file` / `upload-url` / `how-it-works` / `resources` / `authority-dashboard` / `metrics-dashboard` / `my-reports`
- `upload-file` / `upload-url` → `analysis`
- `analysis` → `role-output`
- `role-output` → `confirmation` (Citizen/Journalist/Police) OR `authority-dashboard` (Authority)
- `confirmation` → `landing`

---

### 2. Login Screen: `components/login-page.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/login-page.tsx`

**Component:** `LoginPage`

**Purpose:** Authenticate users and set role-based access

**Props:**
- `onLogin(role, identifier, name, organization, token)`: Callback on successful auth
- `onResourcesClick()`: Navigate to resources page

**State:**
- `role`: Selected role (default: Citizen)
- `identifier`: User input (email/phone/department ID)
- `error`: Error message string
- `loading`: Loading state

**API Call:**
- **Endpoint:** `POST http://127.0.0.1:8000/verify-login`
- **Payload:** `{ role, identifier }`
- **Response:** `{ valid: boolean, user: { official_id, name, organization }, access_token: string }`
- **Error Handling:** Displays error message, shows connection failure

**UI Behavior:**
- Role selector dropdown with 4 options
- Dynamic placeholder based on role (Email/Phone for Citizen, Media ID for Journalist, Department ID for Police, Government ID for Authority)
- Submit button with loading state
- Header with navigation links (About, How it Works, Resources)
- Shield icon branding

---

### 3. Landing Page: `components/landing-page.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/landing-page.tsx`

**Component:** `LandingPage`

**Purpose:** Main dashboard with navigation to all features

**Props:**
- `userRole`: Current user role
- `onUploadClick()`: Navigate to file upload
- `onUrlClick()`: Navigate to URL upload
- `onHowItWorksClick()`: Navigate to how-it-works
- `onResourcesClick()`: Navigate to resources
- `onViewDashboardClick()`: Navigate to authority dashboard (Authority only)
- `onViewMetricsClick()`: Navigate to metrics dashboard
- `onViewMyReportsClick()`: Navigate to my reports
- `onLogout()`: Clear auth state

**UI Components:**
- Header with logo, navigation links, role badge, logout button
- Hero section with "Detect Deepfakes. Preserve Evidence. Enable Action." headline
- Two CTA buttons: "Upload File" (primary) and "Paste URL" (outline)
- 4-step visual flow cards: Upload → Analyze → Verdict → Action
- Trust indicators (End-to-end encryption, Evidence preservation, Legal compliance)
- Footer with links

**Role-Based Features:**
- Metrics button (all authenticated users)
- My Reports button (all authenticated users)
- Authority Dashboard button (Authority role only)

**Navigation:**
- All buttons use callback props to update `currentScreen` in parent
- External links open in new tabs

---

### 4. Upload Screen: `components/upload-screen.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/upload-screen.tsx`

**Component:** `UploadScreen`

**Purpose:** Accept media input (file or URL) with optional source traceability

**Props:**
- `mode`: "file" or "url"
- `initialUrl`: Pre-filled URL from query params
- `onBack()`: Return to landing
- `onAnalyze(data, file)`: Pass analysis result to next screen

**State:**
- `file`: Selected file object
- `url`: URL input string
- `isDragging`: Drag-and-drop state
- `isProcessing`: Processing animation state
- `loading`: API call loading state
- `error`: Error message
- `simulateSafeContent`: Demo toggle for pre-filter simulation
- `showSafeResult`: Show safe content result
- `showSourceFields`: Toggle source detail fields
- `platform`: Platform dropdown (X, Instagram, YouTube, WhatsApp, Facebook, Other)
- `username`: Username/handle input
- `originalUrl`: Original link input
- `processingSteps`: Array of step completion states

**API Call:**
- **Endpoint:** `POST http://127.0.0.1:8000/analyze`
- **Payload:** FormData with `file` field
- **Response:** `AnalyzeResponse` object (see API contracts section)
- **Timeout:** 300 seconds (5 minutes)
- **Error Handling:** Alert with error message, reset processing state

**File Mode Flow:**
1. Drag-and-drop or click to select file
2. File size validation (20MB limit, 100MB warning)
3. Optional source fields (platform, username, original URL)
4. "Begin Analysis" button triggers processing animation
5. Processing steps: Securing evidence → SHA-256 hash → Timestamp → Evidence locked
6. API call to `/analyze`
7. Pass result to `onAnalyze` callback with `SourceInfo` object

**URL Mode Flow:**
1. Paste URL in input field
2. Auto-detect platform from URL (X, Instagram, YouTube, Facebook, WhatsApp)
3. Fetch media from URL (with fallback to mock for demo)
4. Same processing animation and API call as file mode
5. Pass result with verified source info

**Demo Features:**
- "Simulate Pre-Filter (Safe Content)" checkbox
- Shows "No harmful content detected" result if checked
- Skips full analysis for demo purposes

**UI Behavior:**
- Drag-and-drop zone with visual feedback
- File preview with name and size
- Social media platform icons for URL mode
- Collapsible source fields
- Processing animation with step-by-step progress
- Error display with alert

---

### 5. Analysis Result: `components/analysis-result.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/analysis-result.tsx`

**Component:** `AnalysisResult`

**Purpose:** Display multi-stream forensic analysis results with visualizations

**Props:**
- `onContinue()`: Navigate to role-based output
- `onBack()`: Return to landing
- `sourceInfo`: Source information object
- `data`: Full analysis response from backend

**State:**
- `isPlaying`: Video play/pause state
- `showFactCheck`: Toggle fact-check section

**Data Extraction:**
- `detection`: Nested `deepfake_detection` object or fallback to top-level fields
- `isFake`: Boolean derived from label/prediction
- `finalLabel`: Detection label string
- `confidenceValue`: Confidence percentage (0-100)
- `riskLevel`: Risk tier (CRITICAL/HIGH/MEDIUM/LOW)
- `streams`: 5-stream analysis results
- `legalReportUrl`: PDF download URL
- `factCheck`: Fact-check analysis object
- `isVideo`: Boolean for video detection

**UI Sections:**

**1. Main Verdict Banner**
- Risk tier badge (color-coded)
- Origin verification badge (if URL mode)
- Large verdict text ("Likely Synthetic Media" or "Likely Authentic")
- Confidence percentage with radial gauge visualization
- Processing time and submission ID
- Ambient background glow (red for fake, green for real)

**2. Multi-Stream Neural Forensic Analysis (5 Cards)**
- **Spatial Stream:** SRM Noise Forensics with P(Fake) progress bar
- **Frequency Stream:** 2D FFT DCT with P(Fake) progress bar
- **Temporal Stream:** R3D-18 Inter-frame Consistency (N/A for images)
- **Acoustic Stream:** Voice Synthesis RawNet2 (N/A if no audio)
- **Liveness Stream:** rPPG Liveness with pulse detection (N/A for images)

**3. Media & Grad-CAM Visualizations**
- Media preview (video player or image)
- SHA-256 hash display
- "SYNTHETIC PATTERN DETECTED" overlay for fake media
- BSA Sec. 63 Blockchain Chain of Custody verification

**4. Contextual Fact-Check**
- Collapsible section
- Misinformation risk badge
- Claim-by-claim analysis with speaker, verdict, explanation
- Source links with external icons
- "No misinformation analysis" message if unavailable

**5. Continue Button**
- "Escalate and Remediate" button to navigate to role-based output
- Legal Report PDF download button (if available)

**Color Scheme:**
- Background: `#0b0f19` (dark slate)
- Cards: `#0f172a` (slate-900)
- Borders: `#1e293b` (slate-800)
- Text: `#e2e8f0` (slate-200)
- Primary: Indigo/blue
- Verdict colors: Red (fake), Emerald (real)

---

### 6. Role-Based Output: `components/role-based-output.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/role-based-output.tsx`

**Component:** `RoleBasedOutput`

**Purpose:** Display role-specific actions based on detection result

**Props:**
- `userRole`: Current user role
- `sourceUrl`: Original URL (if any)
- `userIdentifier`: User ID
- `userName`: User name
- `userOrganization`: User organization
- `analysisData`: Full analysis response
- `uploadedFile`: File object
- `onAction(reportInfo)`: Callback after action completion
- `onBack()`: Return to analysis

**State:**
- `loading`: Report submission loading state
- `copied`: Hash copy clipboard state
- `submittedReport`: Submitted report object
- `generatingDocs`: Legal doc generation loading state
- `legalDocs`: Generated legal documents array

**Derived Values:**
- `prediction`: Final prediction string
- `isFake`: Boolean for fake detection
- `isReal`: Boolean for real detection
- `confidenceValue`: Confidence percentage
- `mediaHash`: SHA-256 hash
- `filename`: Media filename
- `mediaType`: Media type (image/video)
- `oodFlags`: Out-of-distribution flags

**API Calls:**

**1. Submit Report (Citizen/Journalist/Police/Authority)**
- **Endpoint:** `POST http://127.0.0.1:8000/api/reports/submit`
- **Payload:** FormData with `analysis_json` and optional `file`
- **Response:** `{ success: boolean, report_id: string, status: string, message: string }`
- **Used by:** All roles for case registration

**2. Generate Legal Docs (Police/Authority)**
- **Endpoint:** `POST http://127.0.0.1:8000/api/reports/{reportId}/generate-legal-docs`
- **Payload:** None (POST to report ID)
- **Response:** `{ success: boolean, documents: LegalDocument[], packet_id: string }`
- **Used by:** Police and Authority after case registration

**Role-Specific UI:**

**Citizen:**
- Summary card with verdict and confidence
- "Suspected Deepfake Detected" warning (if fake)
- "Media Verified as Authentic" message (if real)
- "Submit Official Grievance" button (disabled if real)
- Escalates to I4C (Cyber Crime Coordination Center)

**Journalist:**
- Summary card with verdict and confidence
- "Media Verified as Authentic" message (if real)
- "File Grievance Report" button (disabled if real)
- "Cancel & Re-analyze" button
- Registers as secure evidence packet for publication

**Police:**
- Summary card with verdict and confidence
- Evidence Cryptographic Signature card with hash copy button
- Evidence Custody Ledger with timeline (media ingested → hash computed → evidence sealed → detection completed)
- "Register Official Case" button (disabled if real)
- After registration:
  - Success card with case ID and status
  - "Export Log" button (downloads text report)
  - Legal Notice Generation card
  - "Generate Legal Packet" button
  - Generated documents list with download links

**Authority:**
- Administrative Authority Console card
- Description of dashboard capabilities
- "Register Case First" button (if not registered)
- Success message after registration
- "Go to Action Dashboard" button → navigates to authority-dashboard

**Navigation:**
- All roles: `onBack()` returns to analysis screen
- Citizen/Journalist: `onAction()` navigates to confirmation screen
- Police: `onAction()` navigates to confirmation screen
- Authority: `onAction()` navigates to authority-dashboard screen

**UI Features:**
- UnifiedHeader component with back button
- Toast notifications for success/error
- Loading spinners during API calls
- Copy hash to clipboard with toast feedback
- Download legal documents from backend URLs

---

### 7. Action Confirmation: `components/action-confirmation.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/action-confirmation.tsx`

**Component:** `ActionConfirmation`

**Purpose:** Display success screen with tracking info and document access

**Props:**
- `userRole`: Current user role
- `reportInfo`: Report info object with report_id, status, actions, timestamp
- `onStartOver()`: Return to landing

**State:**
- `copied`: Tracking ID copy state
- `showTracking`: Toggle live tracking view
- `loadingTracking`: API loading state
- `trackingReport`: Live report object from database

**API Calls:**

**1. Track Status**
- **Endpoint:** `GET http://127.0.0.1:8000/api/reports/{reportId}`
- **Response:** `{ report: Report }`
- **Used by:** "Track Status" button to fetch live case status

**2. Download Receipt**
- **Endpoint:** `GET http://127.0.0.1:8000/api/reports/{reportId}` (fetch report)
- **Endpoint:** `POST http://127.0.0.1:8000/api/reports/{reportId}/generate-legal-docs` (if no docs)
- **Endpoint:** `GET http://127.0.0.1:8000/api/reports/{reportId}/documents/{packetId}/{filename}` (download)
- **Used by:** "Download Documents" button

**UI Sections:**

**1. Success Banner**
- Large checkmark icon with pulse animation
- "Action Completed Successfully" heading
- "Your report has been submitted and locked in the secure database" message

**2. Completed Actions Checklist (Default View)**
- "Case registered in BharatShield Ledger" ✓
- "Evidence locked in MongoDB GridFS" ✓
- "Authority notification dispatched" ✓

**3. Live Case Tracker (Toggle View)**
- Refresh button with loading state
- Close button to return to checklist
- Current status badge (color-coded)
- Custody log timeline with timestamps and actors
- Generated legal notices list with download links (if available)

**4. Tracking ID Card**
- BharatShield Case Reference label
- Large tracking ID (monospace, selectable)
- Copy button with checkmark feedback
- Description: "Record this Case ID to track investigation progress..."

**5. Timestamp**
- Submitted date and time in Indian locale format

**6. Action Buttons**
- "Start New Analysis" (primary) → returns to landing
- "Download Documents" (outline) → generates and downloads legal docs
- "Track Status" (outline) → toggles live tracking view

**Role-Based Document Filtering:**
- Sensitive documents hidden for Citizen/Journalist:
  - complete_legal_evidence_packet
  - bsa_section_63_part_b
  - cyber_crime_fir_bns
- Police/Authority see all documents

**UI Behavior:**
- Green success theme
- Toast notifications for copy, download, track actions
- Loading spinners during API calls
- Error handling with toast messages
- Support link at bottom

---

### 8. My Reports: `components/my-reports.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/my-reports.tsx`

**Component:** `MyReports`

**Purpose:** Display user's report history with live tracking and document access

**Props:**
- `userRole`: Current user role
- `userIdentifier`: User ID
- `userName`: User name
- `onBack()`: Return to landing

**State:**
- `reports`: Array of report objects
- `selectedReport`: Currently selected report object
- `loadingList`: List loading state
- `loadingDetail`: Detail loading state
- `searchQuery`: Search input string

**API Calls:**

**1. List Reports**
- **Endpoint:** `GET http://127.0.0.1:8000/api/reports`
- **Query Params:** `status` (optional), `limit` (optional)
- **Response:** `{ reports: Report[] }`
- **Used by:** Initial load and refresh button

**2. Get Report Detail**
- **Endpoint:** `GET http://127.0.0.1:8000/api/reports/{reportId}`
- **Response:** `{ report: Report }`
- **Used by:** Clicking on a report in the list

**UI Layout:**
- Two-column layout (list on left, details on right)
- UnifiedHeader component with back button

**Left Column: Report List**
- "Report History" heading with refresh button
- Search box (case ID or file name)
- Scrollable list of reports
- Each report shows:
  - Report ID (monospace)
  - Status badge (color-coded)
  - Filename (truncated)
  - Date
  - Prediction badge with confidence
  - Chevron right indicator
- Selected state with left border highlight
- Empty state with alert icon
- Loading state with spinner

**Right Column: Report Details**
- Header with report ID and refresh button
- Two detail cards:
  - Submitted Media: filename, SHA-256 hash
  - Incident Verdict: prediction, confidence
- Real-Time Custody Timeline:
  - Current status badge
  - Timeline with events, timestamps, actors
- Legal Documents & Receipts:
  - Document type and filename
  - Download button for each doc
  - Role-based filtering (sensitive docs hidden for non-auth)
  - Hidden docs count warning for non-auth users
- Empty state when no report selected
- Loading state with spinner

**Status Badges:**
- Pending Review: amber
- In Investigation: blue
- Resolved: emerald
- Dismissed: slate

**Document Filtering:**
- Same sensitive doc list as action-confirmation
- Warning message for hidden docs

**UI Behavior:**
- Click report in list → load details in right column
- Search filters list in real-time
- Refresh buttons reload data from API
- Download links open in new tabs
- Toast notifications for errors

---

### 9. Authority Dashboard: `components/authority-dashboard.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/authority-dashboard.tsx`

**Component:** `AuthorityDashboard`

**Purpose:** Administrative interface for managing all reports, case status, and takedown notices

**Props:**
- `userRole`: Current user role (should be Police or Authority)
- `userIdentifier`: User ID
- `userName`: User name
- `userOrganization`: User organization
- `onBack()`: Return to landing

**State:**
- `reports`: Array of all reports
- `selectedReport`: Currently selected report
- `loadingList`: List loading state
- `loadingDetail`: Detail loading state
- `reanalyzing`: Re-evaluation loading state
- `generatingDocs`: Legal doc generation loading state
- `updatingStatus`: Status update loading state
- `sendingTakedown`: Takedown notice loading state
- `statusFilter`: Status filter dropdown value
- `searchQuery`: Search input string
- `adminNotes`: Admin notes input
- `newStatus`: New status dropdown value

**API Calls:**

**1. List Reports (with filter)**
- **Endpoint:** `GET http://127.0.0.1:8000/api/reports?status={statusFilter}`
- **Response:** `{ reports: Report[] }`
- **Used by:** Initial load and filter changes

**2. Get Report Detail**
- **Endpoint:** `GET http://127.0.0.1:8000/api/reports/{reportId}`
- **Response:** `{ report: Report }`
- **Used by:** Selecting a report

**3. Re-evaluate Media**
- **Endpoint:** `POST http://127.0.0.1:8000/api/reports/{reportId}/reanalyze`
- **Response:** `{ success: boolean, new_analysis: any, report: Report }`
- **Used by:** "Re-evaluate Media" button

**4. Generate Legal Docs**
- **Endpoint:** `POST http://127.0.0.1:8000/api/reports/{reportId}/generate-legal-docs`
- **Response:** `{ success: boolean, documents: LegalDocument[], packet_id: string }`
- **Used by:** "Generate Legal Packet" button

**5. Update Status**
- **Endpoint:** `PATCH http://127.0.0.1:8000/api/reports/{reportId}/status`
- **Payload:** `{ status: string, admin_notes: string }`
- **Response:** `{ success: boolean, report: Report }`
- **Used by:** Status update form

**6. Send Takedown Notice**
- **Endpoint:** `POST http://127.0.0.1:8000/api/reports/{reportId}/send-takedown`
- **Response:** `{ success: boolean, message: string, takedown_status: string, vibestream_response?: any, warning?: string }`
- **Used by:** "Send Takedown Notice" button

**UI Layout:**
- Two-column layout (case directory on left, case details on right)
- UnifiedHeader component with back button

**Left Column: Case Directory**
- "Case Directory" heading with refresh button
- Search and filter bar:
  - Search input (case ID, media name, reporter name/ID)
  - Status filter dropdown (all, pending_review, under_investigation, resolved, dismissed)
- Scrollable list of all reports
- Each report shows:
  - Report ID (monospace)
  - Status badge
  - Filename (truncated)
  - Date
  - Prediction badge with confidence
  - Chevron right indicator
- Selected state with left border highlight
- Empty state with alert icon
- Loading state with spinner

**Right Column: Case Details (when report selected)**
- Header with report ID and refresh button
- Case Details Cards:
  - Submitted Media: filename, SHA-256 hash
  - Incident Verdict: prediction, confidence
  - Reporter Info: role, identifier, name
  - Admin Notes: editable text area
- Status Update Section:
  - Status dropdown (pending_review, under_investigation, resolved, dismissed)
  - Admin notes textarea
  - "Update Status" button
- Action Buttons:
  - "Re-evaluate Media" → triggers AI re-analysis
  - "Generate Legal Packet" → generates PDF documents
  - "Send Takedown Notice" → sends to VibeStream
- Legal Documents Section:
  - Document type and filename
  - Download button for each doc
- Takedown Status Section:
  - Shows takedown status, sent time, VibeStream response
- Empty state when no report selected
- Loading state with spinner

**Status Update Flow:**
1. Select new status from dropdown
2. (Optional) Add admin notes
3. Click "Update Status"
4. API call to update status
5. Refresh report details
6. Refresh report list
7. Toast notification

**Re-evaluation Flow:**
1. Click "Re-evaluate Media"
2. API call to re-run AI analysis
3. Display new verdict in toast
4. Refresh report details
5. Refresh report list

**Legal Doc Generation Flow:**
1. Click "Generate Legal Packet"
2. API call to generate PDFs
3. Toast notification with packet ID
4. Refresh report details
5. Refresh report list
6. Display download links

**Takedown Notice Flow:**
1. Click "Send Takedown Notice"
2. API call to send to VibeStream
3. Toast notification with status
4. Refresh report details
5. Refresh report list
6. Display takedown response

**UI Behavior:**
- All actions show loading states
- Toast notifications for all actions
- Error handling with toast messages
- Status filter updates list automatically
- Search filters list in real-time
- Download links open in new tabs

---

### 10. Metrics Dashboard: `components/metrics-dashboard.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/metrics-dashboard.tsx`

**Component:** `MetricsDashboard`

**Purpose:** Display forensic metrics, platform spread, use cases, and restricted authority intelligence

**Props:**
- `userRole`: Current user role
- `onBack()`: Return to landing

**State:**
- `reports`: Array of report objects from API
- `loading`: Data loading state
- `selectedUseCase`: Selected use case category (elections, security, scams)

**API Calls:**

**1. List Reports (for metrics)**
- **Endpoint:** `GET http://127.0.0.1:8000/api/reports`
- **Response:** `{ reports: Report[] }`
- **Used by:** Initial load to compute real metrics

**Computed Metrics:**
- `totalIngested`: Total reports count
- `ensembleFake`: Reports with fake prediction and confidence > 50%
- `platformsScanned`: Static "5 Platforms"
- `activeIncidents`: 10% of total reports as campaigns

**UI Sections:**

**1. Headline Section**
- "Social Media Forensic Ledger" badge with Activity icon
- "Forensic Metrics & Spread Dashboard" heading
- Description about real-time multi-platform aggregation

**2. General Metrics Stats Cards (4 cards)**
- Total Files Scanned (Server icon)
- Ensemble-Confirmed (AlertTriangle icon, red)
- Active Channels (Globe icon)
- Coordination campaigns (Radio icon, indigo, animated pulse)

**3. Time-Series Trend Chart**
- "Detection Trends Over Time" heading
- "Weekly deepfake detection volume and confidence distribution" description
- "LIVE UPDATE" indicator with pulsing dot
- Interactive bar chart with 8 weeks of data
- Hover tooltips showing detection count
- Gradient bars (indigo-600 to indigo-400)
- Week labels on x-axis

**4. Platform Spread & Use Case Split (two columns)**

**Platform Spread Chart (left column):**
- "Circulation by Social Media Platform" heading
- Platform breakdown with progress bars:
  - WhatsApp: 46% (7,785 instances) - emerald
  - X (Twitter): 28% (4,738 instances) - sky
  - YouTube: 14% (2,369 instances) - red
  - Instagram: 8% (1,353 instances) - pink
  - Facebook: 4% (679 instances) - blue

**Use Case Focus Switch (right column):**
- "Misinformation Use Cases" heading
- Three tabs: Elections Integrity, Civil Security, Financial Scams
- Tab content shows:
  - Title and description
  - Risk tier badge (CRITICAL or HIGH)
  - Volume Logged stat
  - Primary Subject stat
  - High Impact Case Studies list with platform and volume

**5. Restricted Authority Panel**
- Header with lock/unlock icon based on role
- "Officer Credentials Required" badge for non-elevated roles
- Restricted content for Police/Authority only:
  - Coordinate Circulation Clusters (botnets, server clusters)
  - State-wise Circulation Tiers (Maharashtra, Karnataka, UP, Delhi NCR)
- Locked state shows:
  - Lock icon
  - "Restricted Threat Intelligence" message
  - Description of restricted content
  - Login prompt for ATH/POL department ID

**Mock Data:**
- Platform spread percentages and volumes
- Use case data (elections, security, scams)
- Coordinate clusters (botnet names, source geo, cluster size, target candidate)
- State-wise infection data (state, volume, risk tier)

**UI Behavior:**
- Real data fetching from API for general stats
- Mock data for platform spread and use cases
- Tab switching for use cases
- Hover effects on charts
- Loading state for data fetch
- Role-based access control for restricted section

**Color Scheme:**
- Background: slate-950
- Cards: slate-900/40 with backdrop-blur
- Borders: slate-800/80
- Text: slate-100
- Primary: indigo
- Accents: emerald, red, amber, sky

---

### 11. Resources Page: `components/resources-page.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/resources-page.tsx`

**Component:** `ResourcesPage`

**Purpose:** Display legal and compliance knowledge base

**Props:**
- `onBack()`: Return to previous screen

**UI Sections:**

**Header**
- Back button
- Logo and branding
- "Legal & Compliance Resources" subtitle

**Main Content**

**Section A: Digital Evidence Integrity**
- Bharatiya Sakshya Adhiniyam, 2023 - Section 63
- Three feature cards:
  - Automated Certificate Generation
  - Cryptographic SHA-256 Media Hashing
  - Append-Only Chain-of-Custody Ledgers
- Green theme with CheckCircle icons

**Section B: Generative AI & Intermediary Liability**
- IT Rules 2021 / 2026 Updates
- Three feature cards:
  - Automated Takedown Notice Dispatch Protocol
  - Emergency Timeline: NCII (2-hour window)
  - Standard Timeline: General Deepfake (3-hour window)
- Amber theme with Clock and AlertTriangle icons

**Section C: Punitive Legal Frameworks**
- Bharatiya Nyaya Sanhita (BNS) & Electoral Laws
- Three feature cards:
  - BNS 319: Cheating by Personation
  - BNS 356: Defamation
  - Representation of the People Act Section 123(4)
- Red theme with Gavel and Scale icons

**Footer Note**
- Legal disclaimer
- Shield icon
- Consult qualified legal counsel notice

**UI Behavior:**
- Static content (no API calls)
- Informational only
- No user input
- Back button navigation

---

### 12. How It Works Page: `app/how-it-works/page.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/app/how-it-works/page.tsx`

**Component:** `HowItWorksPage`

**Purpose:** Explain the BharatShield workflow in 5 steps

**Props:**
- `onBack()`: Return to landing (optional)

**Steps Array:**

**Step 1: Submit Suspicious Content**
- Upload file, Paste URL, Share from social media
- Highlights: SHA-256 hash, Timestamp, Evidence sealed
- Note: "Evidence is secured at the moment of submission"

**Step 2: Multi-Layer AI Analysis**
- Visual analysis, Audio analysis, Metadata analysis
- Output: "Likely Synthetic — 87% confidence"
- Note: "With explainable highlights"

**Step 3: Unified Risk Assessment**
- Combines outputs from all analysis layers
- Produces single final verdict

**Step 4: Role-Based Intelligence Delivery (Highlighted)**
- Citizen: Simple verdict + report option
- Journalist: Detailed analysis report
- Police: Court-ready forensic report
- Authority: Takedown notice generation
- Note: "Same analysis, different outputs based on user role"

**Step 5: Automated Action & Response**
- Evidence package generated
- Takedown notice created
- Case forwarded to authorities
- Note: "From detection to enforcement — in one unified system"

**UI Layout:**
- Vertical timeline with gradient line
- Step cards positioned on timeline
- Step number badges on timeline
- Mobile-responsive (step numbers on cards for mobile)
- Arrow connectors between steps
- Highlighted step 4 with pulse animation

**UI Behavior:**
- Animated fade-in on scroll
- Hover effects on cards
- Step 4 highlighted with primary color
- Back button at bottom
- Footer with links

---

### 13. Unified Header: `components/unified-header.tsx`

**File Path:** `/Users/drunkenstein/dev/unysis-unofficial/frontend/components/unified-header.tsx`

**Component:** `UnifiedHeader`

**Purpose:** Reusable global back/navigation top-bar component

**Props:**
- `title`: Main title (e.g., "BharatShield")
- `subtitle`: Subtitle (e.g., "Detection", "Take Action")
- `showBack`: Boolean to show back button
- `onBack()`: Back button callback

**UI Components:**
- Back button (if showBack=true) with ArrowLeft icon
- Shield icon in rounded container
- Title text
- Subtitle text with slash separator
- Premium styling with indigo accents

**Styling:**
- Background: slate-950
- Border: slate-800/80
- Backdrop blur
- Indigo color scheme
- Tracking-wide typography

**Used By:**
- role-based-output.tsx
- my-reports.tsx
- authority-dashboard.tsx
- metrics-dashboard.tsx

---

## C. COMPONENT DEPENDENCY TREE

```
app/page.tsx (MainApp)
├── LoginPage
│   └── UI components (Button, Card, Input, Select)
├── LandingPage
│   └── UI components (Button, Card)
├── UploadScreen
│   ├── UI components (Button, Card, Input, Select)
│   └── API: analyzeFile()
├── AnalysisResult
│   └── UI components (Button, Card)
├── RoleBasedOutput
│   ├── UnifiedHeader
│   ├── UI components (Button, Card, Input)
│   └── API: submitReport(), generateReportLegalDocs()
├── ActionConfirmation
│   ├── UI components (Button, Card)
│   └── API: getReport(), generateReportLegalDocs()
├── AuthorityDashboard
│   ├── UnifiedHeader
│   ├── UI components (Button, Card, Input, Select)
│   └── API: listReports(), getReport(), updateReportStatus(), reanalyzeReport(), generateReportLegalDocs(), sendTakedownNotice()
├── MetricsDashboard
│   ├── UnifiedHeader
│   ├── UI components (Button, Card)
│   └── API: listReports()
├── MyReports
│   ├── UnifiedHeader
│   ├── UI components (Button, Card, Input)
│   └── API: listReports(), getReport()
├── ResourcesPage
│   └── UI components (Button, Card)
└── HowItWorksPage
    └── UI components (Button, Card)
```

---

## D. API CONTRACT EXPECTED BY FRONTEND

### Base URL
`http://127.0.0.1:8000`

### Authentication
- JWT token stored in `localStorage` as `access_token`
- Bearer token in `Authorization` header for protected endpoints

### Endpoints

#### 1. Login Verification
**Endpoint:** `POST /verify-login`
**Request:**
```json
{
  "role": "Citizen|Journalist|Police|Authority",
  "identifier": "string"
}
```
**Response:**
```json
{
  "valid": boolean,
  "user": {
    "official_id": "string",
    "name": "string",
    "organization": "string"
  },
  "access_token": "string"
}
```

#### 2. Analyze Media
**Endpoint:** `POST /analyze`
**Request:** FormData with `file` field
**Response:** `AnalyzeResponse` object
```typescript
{
  submission_id?: string;
  timestamp_utc?: string;
  file?: {
    name: string;
    size_bytes: number;
    size_human: string;
    type?: string;
    media_type: string;
    sha256: string;
  };
  deepfake_detection?: {
    label: string;
    confidence: number;
    risk_level: string;
    is_deepfake: boolean;
    fake_probability: number;
    streams: {
      spatial_texture?: { fake_prob: number | null; label: string };
      frequency_domain?: { fake_prob: number | null; label: string };
      temporal?: { fake_prob: number | null; label: string };
      audio?: { fake_prob: number | null; label: string; available?: boolean; note?: string };
      rppg?: { has_pulse: boolean | null; bvp_snr: number | null; available?: boolean; note?: string };
    };
    metadata_flags?: string[];
    gradcam_url?: string | null;
    processing_ms: number;
  };
  fact_check?: {
    available: boolean;
    note?: string;
    overall_misinfo_risk?: string;
    claims?: Array<{
      claim: string;
      speaker: string;
      verdict: string;
      explanation: string;
      confidence: number;
      sources: Array<{ title: string; url: string; snippet: string }>;
    }>;
  };
  integrity?: {
    sha256: string;
    audit_entry: string;
  };
  legal_report_url?: string | null;
}
```

#### 3. Submit Report
**Endpoint:** `POST /api/reports/submit`
**Request:** FormData with `analysis_json` and optional `file`
**Response:**
```json
{
  "success": boolean,
  "report_id": string,
  "status": string,
  "message": string
}
```

#### 4. List Reports
**Endpoint:** `GET /api/reports`
**Query Params:** `status` (optional), `limit` (optional)
**Response:**
```json
{
  "reports": Report[]
}
```

#### 5. Get Report
**Endpoint:** `GET /api/reports/{reportId}`
**Response:**
```json
{
  "report": Report
}
```

**Report Schema:**
```typescript
{
  _id: string;
  report_id: string;
  reporter: {
    role: string;
    identifier: string;
    name?: string | null;
  };
  analysis: any;
  media_file_id?: string | null;
  media_hash?: string | null;
  media_filename?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  custody_log: CustodyLogItem[];
  reanalysis_history?: ReanalysisItem[];
  legal_documents?: LegalDocument[];
  admin_notes?: string | null;
  takedown_status?: string | null;
  takedown_response?: {
    sent_at?: string;
    vibestream_response?: any;
    payload?: any;
    error?: string;
  } | null;
}
```

#### 6. Update Report Status
**Endpoint:** `PATCH /api/reports/{reportId}/status`
**Request:**
```json
{
  "status": string,
  "admin_notes": string
}
```
**Response:**
```json
{
  "success": boolean,
  "report": Report
}
```

#### 7. Reanalyze Report
**Endpoint:** `POST /api/reports/{reportId}/reanalyze`
**Response:**
```json
{
  "success": boolean,
  "new_analysis": any,
  "report": Report
}
```

#### 8. Generate Legal Documents
**Endpoint:** `POST /api/reports/{reportId}/generate-legal-docs`
**Response:**
```json
{
  "success": boolean,
  "documents": LegalDocument[],
  "packet_id": string
}
```

#### 9. Download Legal Document
**Endpoint:** `GET /api/reports/{reportId}/documents/{packetId}/{filename}?token={token}`
**Response:** File download (PDF)

#### 10. Send Takedown Notice
**Endpoint:** `POST /api/reports/{reportId}/send-takedown`
**Response:**
```json
{
  "success": boolean,
  "message": string,
  "takedown_status": string,
  "vibestream_response?: any,
  "warning?: string
}
```

---

## E. FILES REQUIRED FOR THIS FLOW

### Core Application Files
- `frontend/app/page.tsx` - Main routing controller
- `frontend/app/layout.tsx` - Root layout (not reviewed, assumed standard)
- `frontend/app/globals.css` - Global styles (not reviewed, assumed standard)

### Component Files
- `frontend/components/login-page.tsx` - Login screen
- `frontend/components/landing-page.tsx` - Main dashboard
- `frontend/components/upload-screen.tsx` - Media upload
- `frontend/components/analysis-result.tsx` - Analysis results
- `frontend/components/role-based-output.tsx` - Role-specific actions
- `frontend/components/action-confirmation.tsx` - Success screen
- `frontend/components/authority-dashboard.tsx` - Admin interface
- `frontend/components/metrics-dashboard.tsx` - Metrics display
- `frontend/components/my-reports.tsx` - Report history
- `frontend/components/resources-page.tsx` - Legal resources
- `frontend/components/unified-header.tsx` - Reusable header

### Page Files
- `frontend/app/how-it-works/page.tsx` - How it works page

### API Layer
- `frontend/src/api.ts` - API functions and type definitions

### UI Components (shadcn/ui)
- `frontend/components/ui/button.tsx`
- `frontend/components/ui/card.tsx`
- `frontend/components/ui/input.tsx`
- `frontend/components/ui/select.tsx`
- `frontend/components/ui/label.tsx`
- (and other UI components used)

### Hooks
- `frontend/hooks/use-toast.ts` - Toast notifications (not reviewed, assumed standard)

### Configuration
- `frontend/tailwind.config.ts` - Tailwind configuration (not reviewed)
- `frontend/tsconfig.json` - TypeScript configuration (not reviewed)

---

## F. FRONTEND ASSUMPTIONS BACKEND MUST SATISFY

### 1. Authentication
- Backend must support `/verify-login` endpoint with role-based authentication
- Must return JWT access token for subsequent API calls
- Token must be stored in localStorage as `access_token`
- Bearer token authentication required for protected endpoints

### 2. Analysis Endpoint
- Backend must accept file upload via FormData at `/analyze`
- Must return structured `AnalyzeResponse` with nested `deepfake_detection` object
- Must include 5-stream analysis results (spatial, frequency, temporal, audio, rPPG)
- Must include fact-check analysis with claims and sources
- Must include SHA-256 hash and integrity information
- Must optionally include legal report URL for PDF download
- Must handle timeout (frontend uses 300 seconds)

### 3. Report Management
- Backend must support report submission with analysis JSON and optional file
- Must generate unique report_id
- Must store custody log with timestamps and actors
- Must support status updates (pending_review, under_investigation, resolved, dismissed)
- Must support admin notes
- Must support re-analysis of stored media
- Must support legal document generation (PDFs)
- Must support document download with token authentication
- Must support takedown notice dispatch to external platforms (VibeStream)

### 4. Report Querying
- Backend must support listing all reports with optional status filter
- Must support fetching individual report by ID
- Must return complete report object with all nested data
- Must support search by report_id, media_filename, reporter name/identifier

### 5. Legal Document Generation
- Backend must generate multiple document types:
  - complete_legal_evidence_packet (sensitive)
  - bsa_section_63_part_b (sensitive)
  - cyber_crime_fir_bns (sensitive)
  - Other non-sensitive documents
- Must return document metadata (type, filename, packet_id)
- Must serve documents via download endpoint with token auth

### 6. Takedown Integration
- Backend must integrate with VibeStream admin panel
- Must send takedown notices with proper payload
- Must store takedown response and status
- Must handle errors and warnings from external platform

### 7. Data Storage
- Backend must store media files (MongoDB GridFS assumed)
- Must store analysis results with all stream data
- Must maintain append-only custody logs
- Must support re-analysis history
- Must store legal documents with packet IDs

### 8. Role-Based Access
- Backend must enforce role-based access control
- Police and Authority must have full access to all documents
- Citizen and Journalist must have restricted access to sensitive documents
- Backend must validate JWT tokens and roles

### 9. Error Handling
- Backend must return appropriate HTTP status codes
- Must return error messages in JSON format
- Must handle network errors gracefully
- Must validate input data (file size, format, etc.)

### 10. Performance
- Backend must handle file uploads up to 20MB (100MB with warning)
- Must complete analysis within reasonable time (frontend shows 300s timeout)
- Must support concurrent report queries
- Must serve PDF downloads efficiently

---

## SUMMARY

The BharatShield frontend implements a comprehensive deepfake detection and reporting workflow with:

- **Role-based access** for Citizen, Journalist, Police, and Authority users
- **Multi-stream AI analysis** with visual, audio, and metadata forensics
- **Evidence preservation** with SHA-256 hashing and chain-of-custody tracking
- **Legal compliance** with automated document generation and takedown notices
- **Real-time tracking** of case status and custody logs
- **Administrative dashboard** for managing all reports and case workflows
- **Metrics visualization** for platform spread and use case analysis
- **Premium UI/UX** with warm charcoal backgrounds, indigo accents, and smooth typography

The flow is well-structured with clear separation of concerns, reusable components, and comprehensive API integration for backend communication.
