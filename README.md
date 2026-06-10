
# 2026-A-National-Deepfake-Detection-and-Misinformation-Response-Platform-for-India
https://idea.unisys.com/D9066


# Unysis Deepfake Detection System

## Overview

BharatShield is a comprehensive deepfake detection and misinformation response platform for India. It provides:

- **AI-Powered Detection**: Multi-stream neural forensic analysis (spatial, frequency, temporal, acoustic, liveness)
- **Role-Based Access**: Tailored interfaces for Citizens, Journalists, Police, and Authorities
- **Legal Compliance**: Automated legal document generation compliant with BSA Section 63, IT Rules 2021, and BNS
- **Evidence Preservation**: SHA-256 hashing, chain-of-custody tracking, and MongoDB GridFS storage
- **Takedown Integration**: Automated takedown notice dispatch to platforms like VibeStream
- **Real-Time Tracking**: Live case status updates and custody timeline visualization

## Project Structure

```
unysis-unofficial/
├── backend/                 # FastAPI backend server
│   ├── main.py             # Main application entry point
│   ├── report_routes.py    # Report submission and management
│   ├── auth_routes.py      # Authentication endpoints
│   ├── analyze_routes.py   # Media analysis endpoint
│   └── legal/              # Legal document generation templates
├── frontend/               # Next.js frontend application
│   ├── app/                # App router pages
│   │   ├── page.tsx       # Main routing controller
│   │   └── how-it-works/  # How it works page
│   ├── components/         # React components
│   │   ├── login-page.tsx
│   │   ├── landing-page.tsx
│   │   ├── upload-screen.tsx
│   │   ├── analysis-result.tsx
│   │   ├── role-based-output.tsx
│   │   ├── action-confirmation.tsx
│   │   ├── authority-dashboard.tsx
│   │   ├── metrics-dashboard.tsx
│   │   ├── my-reports.tsx
│   │   ├── resources-page.tsx
│   │   └── unified-header.tsx
│   └── src/
│       └── api.ts          # API client functions
├── ml_pipeline/            # Machine learning pipeline
│   ├── train.py           # Model training script
│   ├── process_data.py    # Data preprocessing
│   └── models/            # Model weights (gitignored)
├── vibestream-demo/        # VibeStream social media platform demo
│   └── src/
│       └── pages/
│           └── Admin.jsx  # Admin panel with cross-verification
```

## Features

### Detection Engine
- **5-Stream Neural Forensic Analysis**:
  - Spatial Texture (SRM Noise Forensics)
  - Frequency Domain (2D FFT DCT)
  - Temporal (R3D-18 Inter-frame Consistency)
  - Acoustic (Voice Synthesis RawNet2)
  - Liveness (rPPG Pulse Detection)
- **Fact-Check Integration**: Contextual misinformation analysis with source verification
- **Grad-CAM Visualization**: Explainable AI with synthetic pattern highlighting

### Role-Based Workflows

**Citizen**:
- Simple verdict display
- Submit grievance to I4C (Cyber Crime Coordination Center)
- Track case status with tracking ID

**Journalist**:
- Detailed analysis report
- Register as evidence packet for publication
- Download legal documents

**Police**:
- Court-ready forensic report
- Evidence cryptographic signature (SHA-256)
- Custody ledger with timeline
- Generate legal notice packet (BSA Section 63, FIR drafts)
- Register official cases

**Authority**:
- Administrative case review dashboard
- Update case status (pending_review, under_investigation, resolved, dismissed)
- Re-evaluate media with AI
- Generate legal documents
- Send takedown notices to platforms
- View all reports with filtering

### Legal Compliance
- **Bharatiya Sakshya Adhiniyam 2023 - Section 63**: Automated certificate generation
- **IT Rules 2021/2026**: Takedown notice dispatch (2-hour emergency for NCII, 3-hour standard)
- **Bharatiya Nyaya Sanhita (BNS)**: Applicable sections for cheating, defamation, electoral interference
- **Chain-of-Custody**: Append-only tamper-evident ledgers

### Dashboards
- **Authority Dashboard**: Case management, status updates, re-evaluation, takedown notices
- **Metrics Dashboard**: Real-time forensic metrics, platform spread, use case analysis
- **My Reports**: Personal report history with live tracking

### Integration
- **VibeStream Integration**: Cross-verification button redirects to BharatShield analysis
- **MongoDB GridFS**: Secure media storage
- **JWT Authentication**: Role-based access control

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- MongoDB
- FFmpeg (for video processing)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run backend server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at `http://127.0.0.1:8000`

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

### VibeStream Demo Setup (Optional)

```bash
cd vibestream-demo

# Install dependencies
npm install

# Run development server
npm start
```

VibeStream demo will be available at `http://localhost:3001`

## API Documentation

### Authentication
- **POST /verify-login**: Authenticate user with role and identifier
- Returns JWT access token for subsequent API calls

### Analysis
- **POST /analyze**: Upload media for deepfake detection
- Accepts file upload via FormData
- Returns multi-stream analysis results with confidence scores

### Reports
- **POST /api/reports/submit**: Submit report with analysis data
- **GET /api/reports**: List all reports (with optional status filter)
- **GET /api/reports/{reportId}**: Get report details
- **PATCH /api/reports/{reportId}/status**: Update report status
- **POST /api/reports/{reportId}/reanalyze**: Re-evaluate media with AI
- **POST /api/reports/{reportId}/generate-legal-docs**: Generate legal documents
- **GET /api/reports/{reportId}/documents/{packetId}/{filename}**: Download legal document
- **POST /api/reports/{reportId}/send-takedown**: Send takedown notice to platform

See `TEAMMATE_FRONTEND_FLOW_AUDIT.md` for detailed API contracts and request/response schemas.

## User Roles

### Citizen
- Identifier: Email or phone number
- Access: Upload, analyze, submit grievance, track status

### Journalist
- Identifier: Media organization ID
- Access: Upload, analyze, register evidence, download reports

### Police
- Identifier: Department ID
- Access: All citizen features + case registration + legal doc generation

### Authority
- Identifier: Government ID
- Access: All police features + authority dashboard + takedown notices

## Legal Frameworks Referenced

- **Bharatiya Sakshya Adhiniyam 2023 - Section 63**: Digital evidence integrity standards
- **IT Rules 2021/2026**: Intermediary liability and takedown timelines
- **BNS 319**: Cheating by personation
- **BNS 356**: Defamation
- **Representation of the People Act Section 123(4)**: Electoral disinformation

## Recent Updates

### Latest Changes
- **Unified Header Component**: Implemented consistent navigation across all screens with back button functionality
- **Authority Dashboard**: Added comprehensive case management with status updates, re-evaluation, and takedown notices
- **Metrics Dashboard**: Enhanced with real-time data fetching, interactive charts, and platform spread visualization
- **Legal Document Generation**: Automated PDF generation for BSA Section 63 certificates, FIR drafts, and compliance notices
- **Role-Based Output**: Refined workflows for Citizen, Journalist, Police, and Authority with appropriate access controls
- **VibeStream Integration**: Cross-verification button redirects to BharatShield analysis page
- **Dynamic Custody Timeline**: Real-time tracking of evidence custody with append-only logs
- **Reanalysis Feature**: Ability to re-evaluate media with updated AI models
- **Document Access Control**: Role-based filtering of sensitive legal documents

### Frontend Flow Audit
Comprehensive frontend flow documentation available in `TEAMMATE_FRONTEND_FLOW_AUDIT.md` including:
- Complete demo flows for all user roles
- Screen-by-screen component documentation
- API contracts and request/response schemas
- Component dependency tree
- Backend requirements and assumptions

## Development Workflow

### Adding New Features
1. Backend: Add routes in `backend/` directory
2. Frontend: Create components in `frontend/components/`
3. API: Update `frontend/src/api.ts` with new endpoints
4. Update routing in `frontend/app/page.tsx`

### Testing
- Backend: Use FastAPI's automatic docs at `http://127.0.0.1:8000/docs`
- Frontend: Access at `http://localhost:3000`
- VibeStream: Access at `http://localhost:3001`

### Code Style
- Backend: Python with PEP 8 compliance
- Frontend: TypeScript with ESLint
- Components: Functional React components with hooks
- Styling: Tailwind CSS with shadcn/ui components

## Dataset and Model Information

Due to repository size constraints, large datasets and model artifacts are **intentionally excluded from version control**.

---

## Ignored Files & Directories

The following directories are excluded via `.gitignore` to comply with GitHub size limits and to keep the repository lightweight and code-focused.

---

### 1. `dataset_raw/` (≈ 41.59 GB, 13,904 files)

Raw video datasets used for training and evaluation.

#### Structure:
- **Celeb-DF**
  - Celeb-real: 158 videos
  - Celeb-synthesis: 795 videos
  - YouTube-real: 250 videos

- **Celeb-DF-v2**
  - Celeb-real: 590 videos
  - Celeb-synthesis: 5,639 videos
  - YouTube-real: 300 videos

- **DFDC Dataset**
  - dfdc_train_part_0: 1,335 videos
  - dfdc_train_part_1: 1,700 videos
  - dfdc_train_part_49: 3,135 videos

#### File Types:
- `.mp4`: 13,899
- `.json`: 3
- `.txt`: 2

#### Reason for Exclusion:
- Extremely large size (40+ GB)
- Public datasets that can be re-downloaded
- Not suitable for version control

---

### 2. `base_deepfake/` (≈ 13.35 GB, 4,015 files)

Pre-processed and structured dataset used for training/validation/testing.

#### Structure:
- **train**
  - real: 1,404 videos
  - fake: 1,404 videos

- **test**
  - real: 302 videos
  - fake: 302 videos

- **val**
  - real: 301 videos
  - fake: 301 videos

#### File Types:
- `.mp4`: 4,014
- `.json`: 1

#### Reason for Exclusion:
- Large storage footprint
- Derived from raw datasets (reproducible)
- Not required to understand or review code

---

### 3. `ml_pipeline/processed_data/` (≈ 8.81 GB, 153,540 files)

Fully processed dataset used for model training (frame/face extraction).

#### Structure:

##### faces
- train: real (21,060), fake (21,060)
- test: real (4,530), fake (4,530)

##### frames
- train:
  - real: 21,060 (~2741 MB)
  - fake: 21,060 (~3996 MB)
- test:
  - real: 4,530 (~562 MB)
  - fake: 4,530 (~835 MB)

##### final
- train: real (21,060), fake (21,060)
- test: real (4,530), fake (4,530)

#### File Types:
- `.jpg`: 153,540

#### Reason for Exclusion:
- High file count (150K+ files)
- Generated data (reproducible via pipeline)
- Not suitable for Git tracking

---

### 4. `ml_pipeline/models/` (Model Weights)

Contains trained model weights and checkpoints.

#### Structure:
- `frame_model.pth` (~15.58 MB)
- `model.pth` (~15.56 MB)

- **checkpoints/**
  - `best_model.pth` (~15.58 MB)
  - `checkpoint_epoch_1.pth` (~46.34 MB)

#### Total Size:
≈ 90+ MB

#### Reason for Exclusion:
- Binary files not suitable for version control
- Frequently updated during training
- Can be regenerated via training pipeline

---

## Summary of Exclusions

| Category | Size | Reason |
|--------|------|--------|
| Raw datasets | ~41.6 GB | Public + too large |
| Base dataset | ~13.3 GB | Derived + large |
| Processed data | ~8.8 GB | Generated + high file count |
| Model weights | ~90 MB | Binary + reproducible |

---

## Justification

All excluded files fall into one or more of the following categories:

- **Large-scale datasets** (not suitable for Git)
- **Derived/generated data** (can be recreated)
- **Binary artifacts** (model weights, checkpoints)
- **High file count directories** (performance issues in Git)

The repository therefore contains only:
- Source code
- Configuration
- Scripts required to regenerate all artifacts

This ensures:
- Lightweight repository
- Faster cloning
- Clean version control practices
- Reproducibility of results
