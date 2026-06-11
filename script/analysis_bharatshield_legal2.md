# Legal Subsystem Analysis (`/bharatshield_legal2`)

The `/bharatshield_legal2` directory is arguably the most specialized component of the BharatShield project. It is responsible for translating raw machine learning detection metrics into **legally admissible, court-ready documentary evidence** formatted to comply with the 2026 Indian legal framework (including the Bharatiya Sakshya Adhiniyam [BSA], Bharatiya Nyaya Sanhita [BNS], and IT Rules).

## Architectural Overview

The system acts as a rules-based legal engine. It ingests deepfake analysis results (confidence, face matching, metadata), identifies the target's status (e.g., ECI Official, Candidate, Public Figure), and automatically routes the incident through the correct statutory pathway to generate specific legal PDFs and eSakshya compliant JSON payloads.

## Core Modules & Files

### 1. `main.py`
The FastAPI application wrapper strictly for the legal microservice.
- Serves endpoints like `/api/v1/generate-legal-packet` which accepts a comprehensive `LegalGenerationRequest` combining system metadata, file info, ML inference data, and risk indicators.
- Acts as the orchestrator: it validates the input, runs the identity resolver, triggers the legal engine, generates PDFs, compiles the cryptographic log, and ultimately returns the signed zip file and PDF paths.

### 2. `resolver.py` & `identity_merge.py`
**Identity Matching & Biometrics**
- `resolver.py` looks at similarity scores and embeddings extracted during the deepfake detection phase and matches them against a hypothetical biometric ledger.
- It determines if the subject of the deepfake is a high-profile target (e.g., Election Commission Official, Political Candidate, or regular citizen).
- `identity_merge.py` contains the logic for deduplicating or merging profiles if a subject matches multiple known entities.

### 3. `engine.py` (The Legal Router)
This is the core decision matrix of the legal module.
- Based on the `ResolvedIdentity` outputted by `resolver.py`, the engine decides which legal statutes have been violated.
- **Routing Paths:**
  - `ECI_OFFICIAL`: Routes to Representation of the People Act (RPA) Section 123(4) and BNS Sections. Generates ECI contempt reports.
  - `CANDIDATE_ACTIVE`: Triggers IT Rules 2026 rapid takedowns and defamation notices.
  - `PUBLIC_FIGURE`: Focuses on BNS 356 (Defamation) and deepfake specific takedowns.
  - `CITIZEN`: Standard IT rules grievances and generic FIR drafts.

### 4. `schemas.py` & `explanation.py`
- **`schemas.py`**: Extensive Pydantic models defining the strict shape of forensic inputs, bounding boxes, spectrogram features, and identity metadata to ensure strict type compliance before legal processing.
- **`explanation.py`**: Translates complex ML arrays and tensors into human-readable legal English. For example, it converts a high FFT anomaly score into a sentence like "Synthetic artifacts detected in frequency domain indicating generative manipulation," suitable for inclusion in a police FIR or affidavit.

### 5. `generator.py`
**Document Drafting (ReportLab)**
This is a massive file dedicated to visually rendering the court documents as PDFs.
- Uses `reportlab` to draw text, tables, and signatures.
- **Generated Documents include:**
  - `BSA Section 63 Part A & B Certificates`: Mandatory certificates for admitting electronic evidence in Indian courts, stating the device was functioning properly and the ML model's confidence scores.
  - `IT Rules Takedown Notice`: Formal directives addressed to social media Grievance Officers demanding removal within strict compliance windows.
  - `Draft Police FIR`: Formatted for local cyber police, automatically citing the correct sections of the BNS.
  - `Representation of the People Act Complaint`: Specific for election-related interference.

### 6. `secure_log.py`
**Chain of Custody and E-Sakshya Packaging**
- Responsible for ensuring that the generated PDFs and the original media cannot be tampered with.
- It compiles all documents into a standardized directory structure (`output/<packet_id>/documents/`).
- It generates an `esakshya_metadata.json` (a JSON-LD payload meant for integration with Indian judiciary portals).
- Finally, it hashes everything and zips it into `evidentiary_packet_<packet_id>.zip` for secure transmission.

### 7. `reporting.py`
Handles escalation protocols and dispatches.
- Maps generated reports to specific authority endpoints (e.g., emailing the ECI Nodal officer, submitting via API to the NCRP portal).

## Summary
The `bharatshield_legal2` folder operates as an autonomous paralegal. By abstracting the complex Indian legal codes into a routing engine (`engine.py`) and combining it with a robust PDF drafting suite (`generator.py`), it reduces the time needed to file a deepfake cybercrime report from days to milliseconds, ensuring every technical metric is preserved under the required evidentiary statutes.
