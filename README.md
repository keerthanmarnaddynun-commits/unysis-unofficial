# Deepfake Detection System

## ⚠️ Dataset Note

The repository does not include large dataset folders such as:
- `base_deepfake/`
- `processed_data/`

### Clarification:
- The **raw datasets** (Celeb-DF and DFDC) were used as the original source.
- `base_deepfake/` is a **derived dataset** created after randomly choosing equal number of real and fake videos from **raw datasets** and then splitting them into train-validate-test sub folders 
- `processed_data/` contains intermediate outputs (frames, faces, final dataset) generated during the pipeline.

### Reason for exclusion:
- These folders are large (GB-scale) and not suitable for Git version control.
- They are excluded to keep the repository lightweight and efficient.

### What is included:
- Trained model: `ml_pipeline/models/frame_model.pth`
- Full pipeline code to regenerate data and retrain the model

