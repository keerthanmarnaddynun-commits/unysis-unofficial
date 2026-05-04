import requests
from pathlib import Path

# API endpoint
url = "http://127.0.0.1:5000/predict/image"

# Folder with CLEAN images
input_dir = Path("test_images_clean")

results = []

for img_path in input_dir.glob("*"):
    if img_path.suffix.lower() not in [".jpg", ".jpeg", ".png", ".webp"]:
        continue

    print(f"Processing: {img_path.name}")

    try:
        with open(img_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files)

        if response.status_code == 200:
            result = response.json()
            print(f"➡️ {img_path.name} → {result}")
            results.append((img_path.name, result))
        else:
            print(f"❌ Failed: {img_path.name} (status {response.status_code})")

    except Exception as e:
        print(f"❌ Error processing {img_path.name}: {e}")

print("\n=== SUMMARY ===")
for name, res in results:
    print(f"{name} → {res}")