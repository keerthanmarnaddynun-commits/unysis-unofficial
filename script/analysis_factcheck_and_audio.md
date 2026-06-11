# Fact-checking & Audio Analysis

BharatShield extends beyond visual deepfake detection by incorporating robust subsystems to analyze the audio track of media and verify the factual integrity of spoken content.

## 1. Fact-checking Pipeline (`/factcheck`)

The fact-checking module is an orchestration pipeline (`pipeline.py`) designed to automatically debunk misinformative audio/video content by cross-referencing spoken claims against live news sources.

### Workflow:
1. **Audio Extraction**: Uses ffmpeg (`utils/video_utils.py`) to rip the audio track from the uploaded video.
2. **Transcription**: Passes the audio to OpenAI's Whisper model (`transcriber.py`) to generate a highly accurate text transcript of the speech.
3. **Claim Extraction (`claim_extractor.py`)**: 
   - Uses **spaCy** NLP (`en_core_web_sm`) to parse the transcript entirely locally.
   - Extracts Named Entities (PERSON, ORG, LAW, EVENT) and numeric quantities (PERCENT, MONEY) to identify "falsifiable claims".
   - It categorizes and prioritizes claims based on their entity type (e.g., PERSON and ORG are "HIGH" priority).
4. **Verification Strategy**:
   - Each claim is queried against **NewsAPI** and **DuckDuckGo News** to find live, recent articles related to the entities and action.
   - **Semantic Verification (`semantic_verifier.py`)**: Uses `sentence-transformers` to measure the semantic similarity and entailment/contradiction between the original spoken claim and the scraped news articles.
5. **Harm Classification (`harm_classifier.py`)**: Passes the transcript through a Zero-Shot classification model (e.g., BART) to flag hate speech, violent rhetoric, or specific algorithmic manipulation markers.

This pipeline degrades gracefully. If an API is offline or Whisper fails, it returns partial results with detailed warnings, ensuring the application doesn't crash during a critical review.

---

## 2. Audio Deepfake Detection (`/audio_analysis`)

While the spatial/FFT models handle visual fakes, the `audio_detector.py` specifically targets AI Voice Cloning, Text-To-Speech (TTS) synthesis, and voice conversion attacks.

### Architecture: RawNet2-small
The system implements a lightweight variant of the RawNet2 architecture, optimized for fast CPU inference (~1.2M parameters).
- **Input**: Raw audio waveform resampled to 16kHz, padded/trimmed to a 4-second chunk.
- **SincConv1d Front-End**: Instead of standard convolutions or MFCCs, the first layer is a Sinc-convolution. This learns low and high cutoff frequencies to create customized band-pass filters directly on the raw waveform, inspired by SincNet.
- **Encoder**: A series of 1D Convolutions, BatchNormalization, and LeakyReLU activations, grouped into Residual Blocks (`ResBlock1D`).
- **Output**: The extracted feature map is pooled (`AdaptiveAvgPool1d`) and passed through a classification head (Linear -> GELU -> Linear) to output a 2-class logit: `[P(REAL), P(FAKE)]`.

### Usage within BharatShield
This module is invoked seamlessly. When a video is uploaded, the backend routes the extracted audio track to this RawNet2-small model. If the `P(FAKE)` exceeds 0.5, the audio is flagged as synthetic, complementing the visual FFT analysis to detect "cheapfakes" where real video is dubbed with cloned AI audio.
