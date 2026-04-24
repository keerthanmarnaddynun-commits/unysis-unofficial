import os
import cv2
import torch
from PIL import Image
from tqdm import tqdm
from facenet_pytorch import MTCNN
import config

class FaceExtractor:
    def __init__(self, fps=config.FPS_EXTRACTION, device=config.DEVICE):
        self.fps = fps
        self.device = device
        # Initialize MTCNN for face detection
        self.mtcnn = MTCNN(keep_all=False, device=self.device, margin=config.FACE_MARGIN)
        
    def extract_faces_from_video(self, video_path, output_dir):
        """
        Extracts frames from a video at self.fps, detects face, and saves it.
        """
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        os.makedirs(output_dir, exist_ok=True)
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error opening video stream or file: {video_path}")
            return
            
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(video_fps / self.fps) if video_fps > 0 else 30
        
        frame_count = 0
        saved_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % frame_interval == 0:
                # Convert BGR to RGB for MTCNN
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb_frame)
                
                # Detect face
                boxes, _ = self.mtcnn.detect(pil_img)
                
                output_path = os.path.join(output_dir, f"{video_name}_frame_{saved_count}.jpg")
                
                if boxes is not None and len(boxes) > 0:
                    # Face detected, use the first one (most prominent)
                    box = boxes[0].astype(int)
                    x1, y1, x2, y2 = box
                    # Ensure coordinates are within image bounds
                    x1 = max(0, x1 - config.FACE_MARGIN)
                    y1 = max(0, y1 - config.FACE_MARGIN)
                    x2 = min(pil_img.width, x2 + config.FACE_MARGIN)
                    y2 = min(pil_img.height, y2 + config.FACE_MARGIN)
                    
                    face_img = pil_img.crop((x1, y1, x2, y2))
                    face_img = face_img.resize(config.IMAGE_SIZE)
                    face_img.save(output_path)
                else:
                    # Fallback to full frame resize
                    resized_img = pil_img.resize(config.IMAGE_SIZE)
                    resized_img.save(output_path)
                    
                saved_count += 1
                
            frame_count += 1
            
        cap.release()
        return saved_count

def process_all_videos(raw_dir, processed_dir):
    extractor = FaceExtractor()
    video_files = [f for f in os.listdir(raw_dir) if f.endswith(('.mp4', '.avi', '.mov'))]
    
    print(f"Found {len(video_files)} videos for processing.")
    
    for video_file in tqdm(video_files, desc="Extracting Faces"):
        video_path = os.path.join(raw_dir, video_file)
        extractor.extract_faces_from_video(video_path, processed_dir)

if __name__ == "__main__":
    process_all_videos(config.RAW_DATA_DIR, config.PROCESSED_DATA_DIR)
