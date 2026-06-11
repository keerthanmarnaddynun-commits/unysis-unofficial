# Machine Learning & FFT Core Pipeline Analysis

The core of BharatShield's deepfake detection lies in its dual-branch ensemble architecture. It simultaneously evaluates the spatial (pixel-level) properties and frequency-domain (spectral) anomalies of media to achieve high reliability.

## Architectural Overview

The system uses an **Orthogonal Ensemble** approach.
1. **Spatial CNN Branch**: Detects visual artifacts, blending inconsistencies, and pixel-level generation errors using an EfficientNet-B4 backbone.
2. **Frequency Domain (FFT) Branch**: Detects synthetic upsampling artifacts and frequency imbalances using a 2D Discrete Fourier Transform fed into a ResNet18 model.
3. **Fusion Engine**: Uses a calibrated logistic regression model to weigh the outputs of both branches, yielding a final confidence score and reliability metric.

---

## 1. Top-Level Inference (`image_inference.py`)
This script (`image_inference.py`) orchestrates the entire inference pipeline for a single image or video frame.
- **Preprocessing (MTCNN)**: It first attempts to run MTCNN to detect and crop the face from the image. If the face is too small or absent, it falls back to analyzing the full frame.
- **Branch Execution**:
  - `run_cnn_branch()`: Prepares the image (Normalizes using ImageNet stats) and passes it through the loaded CNN model.
  - `run_fft_branch()`: Applies a 2D FFT to extract the magnitude spectrum of the image. It optionally applies a **Radial Emphasis Mask** to highlight high-frequency boundaries (where synthetic artifacts often live), normalizes it, and passes it to the FFT model.
- **Fusion & Tristate Logic (`fuse_logistic`)**:
  - Takes the raw logits from both CNN and FFT branches.
  - Applies **Platt Scaling** (learned during training/validation) to convert logits to calibrated probabilities.
  - Executes the `FusionBundle` (usually a trained logistic regression equation) to get the final `prob_final`.
- **Reliability Assessment**: Evaluates the agreement between the two branches (`CNN vs FFT disagreement`), checks Out-Of-Distribution (OOD) flags (like low resolution), and assigns a final reliability tag ("HIGH", "MEDIUM", "LOW").

---

## 2. Spatial CNN Training (`train_deepfake_detection.py`)
This is the production-grade training script for the spatial branch.
- **Model**: `EfficientNetB4Binary`. It leverages a pre-trained EfficientNet-B4 trunk, replacing the classification head with a custom Dropout -> Linear(512) -> GELU -> Dropout -> Linear(1) stack.
- **Loss Function (`FocalLossSigmoid`)**: Uses a binary focal loss with label smoothing. This heavily penalizes the model for being confidently wrong and mitigates class imbalance.
- **Augmentations (Albumentations)**: Employs a brutal augmentation pipeline specifically designed to force the model to learn deep semantic artifacts rather than superficial compression noise. It includes `ImageCompression` (JPEG/WebP), `Downscale`, `GaussianBlur`, `ISONoise`, `CoarseDropout`, and a custom `simulate_social_media_numpy` step mimicking extreme WhatsApp/Twitter compression.
- **Training Techniques**: Uses OneCycleLR scheduling, Mixed Precision (`torch.amp`), Exponential Moving Average (`ModelEMA`) for weight stabilization, and MixUp (logits supervision) to improve generalization.

---

## 3. Fast Fourier Transform Subsystem (`/fft`)
The frequency domain branch is contained entirely within the `/fft` directory.
- **`fft_preprocess.py`**: Converts spatial RGB images into frequency spectrums using `np.fft.fft2` and `np.fft.fftshift`. It extracts the log-magnitude spectrum, making frequency peaks visible to the neural network.
- **`fft_model.py`**: Wraps a `ResNet18` architecture modified to accept 1-channel (or specific YCbCr) spectrum inputs instead of standard RGB.
- **`fusion_pipeline.py` & `fusion_calibrate.py`**: These scripts are used post-training. They take a validation dataset, run both the CNN and FFT models to collect logits, and fit a `PlattCalibrator`. They then evaluate whether a `WeightedFusion` (simple weighted average) or `LogisticFusion` (logistic regression on the linear terms) yields a higher AUC, saving the winning parameters into a serialized `fusion_bundle`.

## Summary
BharatShield avoids the common pitfall of relying on a single spatial CNN (which are easily fooled by heavy JPEG compression). By forcing a secondary evaluation in the frequency domain—where GAN and Diffusion model upsampling leaves distinct grid-like spectral signatures—and fusing the results via a calibrated logistic model, the architecture achieves a highly robust, courtroom-defensible "confidence" score.
