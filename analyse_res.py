import os
from collections import Counter
from PIL import Image

train_dir = r"D:\forsen\final_dataset_aligned"
eval_file = r"D:\forsen\sampled_images_1000.txt"

def analyze_dataset(paths, label_func):
    res_dist = Counter()
    res_real = Counter()
    res_fake = Counter()
    widths = []
    heights = []
    min_res = None
    max_res = None
    min_area = float('inf')
    max_area = 0

    for path in paths:
        try:
            with Image.open(path) as img:
                w, h = img.size
                res = f"{w}x{h}"
                label = label_func(path)
                
                res_dist[res] += 1
                if label == "REAL":
                    res_real[res] += 1
                elif label == "FAKE":
                    res_fake[res] += 1
                    
                widths.append(w)
                heights.append(h)
                
                area = w * h
                if area < min_area:
                    min_area = area
                    min_res = res
                if area > max_area:
                    max_area = area
                    max_res = res
        except Exception:
            pass
            
    if not widths:
        return {}
        
    avg_w = sum(widths) / len(widths)
    avg_h = sum(heights) / len(heights)
    
    return {
        "dist": res_dist,
        "dist_real": res_real,
        "dist_fake": res_fake,
        "min_res": min_res,
        "max_res": max_res,
        "avg_w": avg_w,
        "avg_h": avg_h,
        "total": len(widths)
    }

# 1. Train paths
print("Finding train paths...")
train_paths = []
if os.path.exists(train_dir):
    for root, _, files in os.walk(train_dir):
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                train_paths.append(os.path.join(root, f))
                
def train_label_func(path):
    parts = path.lower().split(os.sep)
    return "FAKE" if "fake" in parts else "REAL"
    
train_stats = analyze_dataset(train_paths, train_label_func)

# 2. Eval paths
print("Finding eval paths...")
eval_paths = []
eval_labels = {}
if os.path.exists(eval_file):
    with open(eval_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            parts = line.strip().split("|", 1)
            if len(parts) == 2:
                eval_paths.append(parts[1])
                eval_labels[parts[1]] = parts[0]
        
def eval_label_func(path):
    return eval_labels[path]
    
eval_stats = analyze_dataset(eval_paths, eval_label_func)

def print_stats(name, stats):
    print(f"\n{'='*50}\n{name} Analysis ({stats['total']} images)\n{'='*50}")
    print(f"Average: {stats['avg_w']:.1f}x{stats['avg_h']:.1f}")
    print(f"Min res: {stats['min_res']} | Max res: {stats['max_res']}")
    
    print("\nTop 20 Resolutions:")
    for res, count in stats["dist"].most_common(20):
        print(f"  {res}: {count}")
        
    print("\nREAL Top Resolutions:")
    for res, count in stats["dist_real"].most_common(10):
        print(f"  {res}: {count}")
        
    print("\nFAKE Top Resolutions:")
    for res, count in stats["dist_fake"].most_common(10):
        print(f"  {res}: {count}")

if train_stats: print_stats("Training Dataset (final_dataset_aligned)", train_stats)
if eval_stats: print_stats("Evaluation Dataset (sampled_images_1000.txt)", eval_stats)

