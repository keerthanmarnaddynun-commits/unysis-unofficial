import sys
sys.path.append('.')
from pathlib import Path
from ml.audio_extractor import extract_audio
from ml.audio_detector import analyze_audio

print("Extracting...")
meta = extract_audio(Path('../test_audio_video.mp4'))
print("Extracted:", meta)

if meta.get("available") and "wav_path" in meta:
    print(f"Analyzing {meta['wav_path']}...")
    res = analyze_audio(Path(meta['wav_path']))
    print("Analyzed:", res)
else:
    print("Not available")