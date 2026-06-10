import subprocess
import os
from pathlib import Path
import tempfile
import soundfile as sf
import traceback

def extract_audio(video_path: Path) -> dict:
    """
    Extracts the audio track from a video file using ffmpeg.
    Returns a dictionary containing the audio extraction metadata.
    """
    from pathlib import Path
    video_path = Path(video_path)
    
    audio_meta = {
        "available": False,
        "extraction_status": "FAILED",
        "duration_sec": 0.0,
        "sample_rate": 0,
        "channels": 0,
        "file_size_kb": 0.0,
        "decision": "NOT_ANALYZED",
        "fake_score": None,
        "confidence_level": "UNKNOWN",
        "quality": "UNKNOWN",
        "suspicious_segments": [],
        "explanation": "Audio deepfake analysis not enabled yet."
    }
    
    # Create a temporary output file path
    temp_dir = tempfile.gettempdir()
    audio_out_path = Path(temp_dir) / f"{video_path.stem}_audio.wav"
    
    try:
        # ffmpeg command to extract 16kHz mono WAV
        cmd = [
            "ffmpeg", 
            "-y", 
            "-i", str(video_path), 
            "-vn", 
            "-acodec", "pcm_s16le", 
            "-ar", "16000", 
            "-ac", "1", 
            str(audio_out_path)
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        stderr = result.stderr.lower()
        if result.returncode != 0:
            # Check if failure is due to no audio stream existing
            if "output file is empty" in stderr or "does not contain any stream" in stderr:
                audio_meta["extraction_status"] = "NO_AUDIO"
            else:
                audio_meta["extraction_status"] = "FAILED"
                print(f"ffmpeg failed: {stderr}")
            return audio_meta
            
        if not audio_out_path.exists():
            # Sometimes ffmpeg succeeds but writes nothing if stream was silent/empty
            audio_meta["extraction_status"] = "NO_AUDIO"
            return audio_meta
            
        # Check size
        file_size_bytes = os.path.getsize(str(audio_out_path))
        if file_size_bytes < 100: # Too small to be valid WAV
            audio_meta["extraction_status"] = "NO_AUDIO"
            return audio_meta
            
        # Parse metadata
        with sf.SoundFile(str(audio_out_path)) as f:
            audio_meta["duration_sec"] = float(f.frames) / f.samplerate
            audio_meta["sample_rate"] = f.samplerate
            audio_meta["channels"] = f.channels
            
        audio_meta["file_size_kb"] = float(file_size_bytes) / 1024.0
        audio_meta["available"] = True
        audio_meta["extraction_status"] = "SUCCESS"
        
        audio_meta["wav_path"] = str(audio_out_path)
        
    except Exception as e:
        audio_meta["extraction_status"] = "FAILED"
        print(f"Exception extracting audio: {e}")
        traceback.print_exc()
        
    return audio_meta
