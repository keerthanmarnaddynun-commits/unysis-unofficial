# Backend Analysis (`/backend`)

The `/backend` directory contains the core API services for the BharatShield platform. It acts as the central hub bridging the front-end user interfaces (both the main platform and the VibeStream demo) with the underlying Machine Learning inference engines, report management, and legal document generation modules.

## Architectural Overview

The backend is built primarily using **FastAPI**. It has recently transitioned away from Flask (legacy code still visible in `app.py`) to fully leverage FastAPI's asynchronous capabilities, performance, and built-in data validation via Pydantic. 

It handles:
1. **File Uploads & Media Processing**: Ingestion of images and videos.
2. **Machine Learning Inference**: Direct invocation of computer vision models (CNN, FFT) and audio spoofing models.
3. **Report & Ledger Management**: A MongoDB-based authority reporting service that stores cases and media using GridFS.
4. **Legal Escelation Pipeline**: Calling legal PDF generation tools and pushing takedown notices to third-party endpoints.

## Core Files & Modules

### 1. `main.py`
This is the **primary entry point** for the FastAPI server. 
- **Initialization**: Sets up logging, environment variables, CORS (allowing `localhost:3000` and `localhost:4000`), and mounts a static directory (`/evidence`) for serving generated visual evidence.
- **Startup Events**: On startup, it attempts to initialize the `ReportService` (MongoDB connection) and pre-load all heavyweight ML models (CNN, FFT, fusion bundles, device placement via `get_img_models()`).
- **Endpoints**:
  - `POST /analyze`: Main endpoint to analyze an uploaded image or video. It supports a `SMOKE_TEST_MODE` to return immediate mock data and PDFs for demonstrations without running heavy ML inference. In production mode, it routes images to `infer_image()` and videos to `predict_video()` while also performing audio extraction and analysis via `analyze_audio()`. It fuses video and audio results, computes temporal smoothing across frames, and generates PDF reports.
  - `POST /predict/video`: A dedicated endpoint strictly for video processing, handling file chunking and running `ml.inference.predict_video`.
  - `POST /verify-login`: Integrates with the MongoDB `authorized_ids` collection to issue JWT access tokens for authenticated roles (Authority, Nodal Officer, etc.).

### 2. `report_service.py`
This module defines the `ReportService` class which abstracts interactions with MongoDB using the asynchronous `motor` driver.
- **Database & Storage**: Connects to the configured Mongo instance and initializes an `AsyncIOMotorGridFSBucket` to securely store forensic media (images/videos) ensuring chain-of-custody.
- **Core Methods**:
  - `store_media()` / `retrieve_media()`: Handles GridFS reading and writing, saving SHA256 checksums alongside files.
  - `create_report()`: Generates a case ID (e.g. BS-12345), stores analysis payloads, logs custody events, and saves the reporter's context.
  - `list_reports()`, `get_report()`, `update_status()`: Standard CRUD operations with role-based filtering logic (Authority users can see all, others only their own).
  - `add_reanalysis()`, `add_legal_documents()`, `update_takedown_status()`: Methods for appending legal action trails to the report document.

### 3. `report_routes.py`
Provides the FastAPI routing (`/api/reports`) for all grievance ledger activities.
- **Dependency Injection**: Relies on `get_current_user` from `auth.py` to ensure endpoints are secured.
- **Endpoints**:
  - `POST /submit` & `POST /submit-json`: Allows users to submit an analyzed media file as a formal report. It enforces that only files predicted as "Fake" or "Synthetic" can be escalated. 
  - `GET /`, `GET /{report_id}`: Fetching ledger reports.
  - `POST /{report_id}/reanalyze`: Allows an authority to rerun deepfake inference on the sealed evidence stored in GridFS.
  - `POST /{report_id}/generate-legal-docs`: Triggers the BharatShield legal sub-module to draft statutory notices (BSA, BNS, IT Rules) and append them to the report.
  - `POST /{report_id}/send-takedown`: A critical interoperability endpoint that transmits an HTTP POST takedown notice to the external VibeStream Demo Server (`localhost:4001/api/takedown`).

### 4. `auth.py`
Provides JWT (JSON Web Token) creation and validation.
- Employs `jose` for HS256 JWT encoding.
- Supplies the `get_current_user` FastAPI dependency which intercepts bearer tokens, validates them, and injects user identity into routes.

### 5. `app.py`
A **deprecated Flask implementation** kept presumably for backward compatibility or reference. It implements `/analyze`, `/predict/image`, and `/predict/video` but lacks the async features, database ledger, and robust error handling present in `main.py`.

### 6. `/ml` (Sub-directory)
Contains the bridging logic and legacy ML hooks.
- **`audio_detector.py` / `audio_extractor.py`**: Interacts with the `aasist` module to extract WAV files from MP4s and evaluate them for voice spoofing.
- **`inference.py`**: A wrapper for executing video inference frame-by-frame and calculating average confidence scores.
- **`pdf_generator.py`**: Uses ReportLab to generate visual summary PDFs (different from the legal affidavits) detailing bounding boxes, confidence timelines, and heatmaps for users.
- **`fusion.py`**: Combines multimodal outputs (video + audio) to yield a final overarching reliability and fake score.

## Summary
The backend is highly sophisticated, focusing heavily on **state management and legal auditability**. Rather than just serving an ML model, it ensures every piece of media evaluated is cryptographically hashed, securely stored in GridFS, tied to an authenticated reporter, and can directly orchestrate legal takedown actions against external platforms (like VibeStream).
