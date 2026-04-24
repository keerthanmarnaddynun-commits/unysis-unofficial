import os
import sys
import torch
import torch.nn.functional as F
import argparse
import glob
from PIL import Image

# Add src to Python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

import config
from model import DeepfakeClassifier
from face_extractor import FaceExtractor
from preprocess import get_transforms

def predict_video(video_path, model_path):
    if not os.path.exists(video_path):
        print(f"Error: Video file {video_path} not found.")
        return None, None
        
    device = config.DEVICE
    
    # 1. Load Model
    model = DeepfakeClassifier(pretrained=False).to(device)
    if os.path.exists(model_path):
        checkpoint = torch.load(model_path, map_location=device)
        if 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
        else:
            model.load_state_dict(checkpoint)
    else:
        print(f"Warning: Model weights not found at {model_path}. Using uninitialized model.")
        
    model.eval()
    
    # 2. Extract Faces
    print(f"Extracting faces from {video_path}...")
    temp_dir = os.path.join(config.DATA_DIR, 'temp_inference')
    extractor = FaceExtractor(fps=config.FPS_EXTRACTION, device=device)
    extracted_count = extractor.extract_faces_from_video(video_path, temp_dir)
    
    if extracted_count == 0 or extracted_count is None:
        print("No frames extracted. Cannot perform prediction.")
        return None, None
        
    # 3. Predict on Frames
    _, val_transform = get_transforms()
    frame_probs = []
    
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    frame_files = glob.glob(os.path.join(temp_dir, f"{video_name}_frame_*.jpg"))
    
    with torch.no_grad():
        for frame_file in frame_files:
            img = Image.open(frame_file).convert('RGB')
            tensor_img = val_transform(img).unsqueeze(0).to(device)
            
            outputs = model(tensor_img)
            probs = F.softmax(outputs, dim=1)
            fake_prob = probs[0][1].item() # Probability of class 1 (FAKE)
            frame_probs.append(fake_prob)
            
    # 4. Cleanup Temp Files
    for f in frame_files:
        os.remove(f)
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass
        
    if not frame_probs:
        print("No valid face images found for prediction.")
        return None, None
        
    # 5. Aggregate Predictions
    final_score = sum(frame_probs) / len(frame_probs)
    final_label = "FAKE" if final_score > 0.5 else "REAL"
    
    print(f"\n--- Prediction Results ---")
    print(f"Video: {os.path.basename(video_path)}")
    print(f"Frames analyzed: {len(frame_probs)}")
    print(f"Confidence Score (Fake Prob): {final_score:.4f}")
    print(f"Final Verdict: {final_label}")
    print(f"--------------------------\n")
    
    return final_label, final_score

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict if a video is Real or Fake.")
    parser.add_argument("--video", type=str, required=True, help="Path to the video file")
    parser.add_argument("--model", type=str, default=os.path.join(config.CHECKPOINT_DIR, "best_model.pth"), help="Path to the model weights")
    args = parser.parse_args()
    
    predict_video(args.video, args.model)
