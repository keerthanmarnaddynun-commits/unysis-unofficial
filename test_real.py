import requests
from pathlib import Path

url = "http://127.0.0.1:5000/predict/image"
# input_dir = Path("test_real_images")
input_dir = Path("test_real_images")

correct = 0
total = 0

print("🚀 Testing REAL images only...\n")
# print("🚀 Testing FAKE images only...\n")

for img_path in input_dir.glob("*"):
    if img_path.suffix.lower() not in [".jpg", ".jpeg", ".png", ".webp"]:
        continue

    print(f"Processing: {img_path.name}")

    try:
        with open(img_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files, timeout=30)

        if response.status_code == 200:
            result = response.json()

            pred = result.get("label", "unknown")
            conf = result.get("confidence", 0)

            print(f"➡️ Pred: {pred} ({conf:.4f})")

            # Since all images are FAKE
            if pred == "real":
                #  if pred == "real": for real 
                correct += 1

            total += 1

        else:
            print(f"❌ Failed: {img_path.name}")

    except Exception as e:
        print(f"❌ Error: {e}")

print("\n=== FINAL RESULT ===")
print(f" Accuracy: {correct}/{total} = {correct/total if total else 0:.2f}")