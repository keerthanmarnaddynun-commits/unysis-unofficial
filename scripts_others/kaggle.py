import os
import kagglehub

# 1. Define and create the path if it doesn't exist
cache_path = r"D:\forsen"
if not os.path.exists(cache_path):
    os.makedirs(cache_path)

# 2. Set the environment variable
os.environ["KAGGLEHUB_CACHE"] = cache_path

# 3. Download (will now go to D:\forsen\datasets\...)
path = kagglehub.dataset_download("arnaud58/flickrfaceshq-dataset-ffhq")

print("Path to dataset files:", path)