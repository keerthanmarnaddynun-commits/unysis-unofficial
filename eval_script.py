import os
import random
import subprocess
import json

random.seed(42)

def get_images(folder, count):
    imgs = []
    for root, dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                imgs.append(os.path.join(root, f))
    return random.sample(imgs, count)

real_imgs = get_images(r'D:\forsen\final_dataset\real', 500)
fake_imgs = get_images(r'D:\forsen\final_dataset\fake', 500)

with open(r'D:\forsen\sampled_images_1000.txt', 'w') as f:
    for p in real_imgs:
        f.write(f"REAL|{p}\n")
    for p in fake_imgs:
        f.write(f"FAKE|{p}\n")
print("Sampled 1000 images and saved to sampled_images_1000.txt")

results = []

def run_inf(path, gt):
    cmd = [
        r'D:\envs\gpu_env\python.exe', '-B', '-u', 'image_inference.py',
        '--input_path', path,
        '--face_crop'
    ]
    env = os.environ.copy()
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONPATH'] = ''
    out = subprocess.check_output(cmd, env=env, text=True)
    
    # Parse output
    # CNN    : FAKE (0.958)
    cnn_prob = None
    fft_prob = None
    fusion_prob = None
    final_label = None
    
    for line in out.splitlines():
        if line.startswith('CNN    :'):
            # CNN    : FAKE (0.958)
            parts = line.split('(')
            cnn_prob = float(parts[1].replace(')', '').strip())
        elif line.startswith('FFT    :'):
            parts = line.split('(')
            fft_prob = float(parts[1].replace(')', '').strip())
        elif line.startswith('Fusion :'):
            parts = line.split('(')
            fusion_prob = float(parts[1].replace(')', '').strip())
            final_label = parts[0].split(':')[1].strip()
            
    results.append({
        'image': os.path.basename(path),
        'gt': gt,
        'cnn': cnn_prob,
        'fft': fft_prob,
        'fusion': fusion_prob,
        'final': final_label
    })

print("Running REAL...")
for p in real_imgs:
    run_inf(p, 'REAL')

print("Running FAKE...")
for p in fake_imgs:
    run_inf(p, 'FAKE')

with open(r'D:\forsen\eval_results_1000_jpeg95.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Done!")
