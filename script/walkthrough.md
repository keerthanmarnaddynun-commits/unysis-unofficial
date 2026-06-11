# Unisys Platform (BharatShield) Technical Evaluation Summary

Welcome to the comprehensive technical evaluation of the BharatShield project. This summary provides a high-level overview of the entire system architecture, with links to detailed, module-specific markdown reports.

## Project Overview
BharatShield is an end-to-end ecosystem designed to combat deepfakes, synthetic media, and misinformation. It bridges the gap between deep-learning forensic analysis and real-world legal enforcement.

The project is structured into several core modules:

1. **[Backend API & Microservices](file:///C:/Users/srujan/.gemini/antigravity-ide/brain/f059facc-6c86-40d8-ae65-bb5840abbace/analysis_backend.md)**
   - Powered by **FastAPI**, serving as the central nervous system.
   - Handles media ingestion, routes tasks to ML engines, and interacts with **MongoDB GridFS** for scalable, high-throughput evidence storage.
   - Manages asynchronous webhook callbacks to third-party social media platforms.

2. **[Machine Learning & Fast Fourier Transform (FFT)](file:///C:/Users/srujan/.gemini/antigravity-ide/brain/f059facc-6c86-40d8-ae65-bb5840abbace/analysis_fft_and_ml.md)**
   - Employs an **Orthogonal Ensemble** strategy.
   - **Spatial CNN**: An EfficientNet-B4 model trained with brutal augmentations (via Albumentations) to catch semantic artifacts and blending errors.
   - **Frequency Domain (FFT)**: A ResNet18 model that analyzes the 2D magnitude spectrum of the image to spot upsampling artifacts common in GANs and Diffusion models.
   - Fuses outputs using Platt scaling and logistic regression for a highly reliable confidence score.

3. **[Audio Analysis & Fact-Checking](file:///C:/Users/srujan/.gemini/antigravity-ide/brain/f059facc-6c86-40d8-ae65-bb5840abbace/analysis_factcheck_and_audio.md)**
   - **Audio Detection**: Implements **RawNet2-small**, processing raw waveforms with a SincConv1d layer to detect AI voice cloning and TTS.
   - **Fact-Checking Pipeline**: Uses OpenAI Whisper to transcribe audio, **spaCy** NLP to extract named entities/claims, and `sentence-transformers` to fact-check those claims against live NewsAPI/DuckDuckGo articles.

4. **[Legal Engineering & Enforcement (`bharatshield_legal2`)](file:///C:/Users/srujan/.gemini/antigravity-ide/brain/f059facc-6c86-40d8-ae65-bb5840abbace/analysis_bharatshield_legal2.md)**
   - Translates raw ML probabilities into actionable, court-admissible legal documents.
   - Uses a strict Rules Engine (`rules.py`) to classify violations under specific Indian IT Act / BNS legal codes based on the severity and content context.
   - Automatically generates formal PDF Takedown Notices and Spatial Forensic Affidavits using `ReportLab`.

5. **[Metadata & Cryptographic Integrity](file:///C:/Users/srujan/.gemini/antigravity-ide/brain/f059facc-6c86-40d8-ae65-bb5840abbace/analysis_metadata_and_tools.md)**
   - Establishes a **BSA-compliant Audit Chain**.
   - Computes SHA-256 hashes of all ingested media via chunked streams.
   - Maintains a tamper-evident HMAC-SHA256 log where every entry is chained to the previous one, ensuring the entire evidence custody timeline is mathematically verifiable.

6. **[Frontend Applications & Social Media Demo](file:///C:/Users/srujan/.gemini/antigravity-ide/brain/f059facc-6c86-40d8-ae65-bb5840abbace/analysis_frontend_and_demo.md)**
   - **BharatShield Portal (Next.js)**: The official dashboard where Citizens, Journalists, and Police interact. Features highly detailed visual feedback (GradCAMs, timelines, confidence gauges).
   - **VibeStream Demo (React/Express)**: A mock social media platform used to tangibly demonstrate the end-to-end capability. Users can flag deepfakes on VibeStream, analyze them in BharatShield, and watch the BharatShield legal engine automatically trigger a takedown webhook back to VibeStream.

## How to use this analysis
These documents are designed to provide you with an exhaustive technical understanding of every component in the repository. Before your evaluation, review the linked markdown artifacts to familiarize yourself with the architectural decisions, fallback mechanisms, and cryptographic integrity measures that make BharatShield a production-ready compliance tool.
