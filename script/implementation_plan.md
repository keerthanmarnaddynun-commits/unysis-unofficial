# Codebase Analysis Plan for `unisys-unofficial`

The goal is to analyze the entire repository and create detailed, descriptive markdown files documenting every program and script in each folder. 

## Proposed Changes

The repository is divided into several logical areas: Machine Learning/Deepfake Detection, Legal/Compliance, Web Frontends, Backend APIs, Fact-Checking, Audio Analysis, and utility tools. I will create the following markdown artifacts to cover the codebase exhaustively.

### 1. `analysis_backend.md`
- Explore the `/backend` folder.
- Document FastAPI endpoints, ML interface (`model_interface`), `legal_integration.py`, authentication, and routing logic.

### 2. `analysis_bharatshield_legal2.md`
- Detail the `/bharatshield_legal2` folder.
- Explain the end-to-end legal pipeline (identity resolution, explanation generation, rules engine, ReportLab PDF generation, secure hashing/eSakshya packaging).

### 3. `analysis_frontend_and_demo.md`
- Analyze the React/Next.js applications.
- Document the main `/frontend` folder and the `/vibestream-demo` application.
- Explain component structure, API connections, state management, and UI architecture.

### 4. `analysis_fft_and_ml.md`
- Document the `/fft` (Fast Fourier Transform) image analysis pipeline.
- Cover `/DeepfakeBench` or top-level ML training scripts (`train_deepfake_detection.py`, `test_cnn.py`, `image_inference.py`).
- Explain datasets, models, preprocessing, and fusion methods.

### 5. `analysis_factcheck_and_audio.md`
- Explore the `/factcheck` module (claim extraction, NewsAPI/DuckDuckGo checking, semantic verification).
- Explore the `/audio_analysis` and `/aasist` (Audio Anti-Spoofing) folders.

### 6. `analysis_metadata_and_tools.md`
- Document `/metadata_analysis` (EXIF and hashing).
- Document `/tools` and `/scripts_others` (dataset auditing, kaggle scripts, sampling).

## Verification Plan
- Ensure all relevant source code files (.py, .js, .tsx) have been read.
- Confirm each artifact contains detailed descriptions, file relationships, and flow diagrams where appropriate.
- Validate that the markdown generated is highly descriptive and elaborate as requested.

## Open Questions
- Are there any specific directories you want me to prioritize or skip (e.g. `node_modules`, `.next`, `test_images_2` which do not contain our core source code)?
