import sys
import json

path = sys.argv[1]
print("Reading:", path)
with open(path, "r") as f:
    data = json.load(f)

fft_correct = 0
cnn_correct = 0
fusion_correct = 0

fft_fp = 0
fft_fn = 0

for x in data:
    gt = x["gt"]

    fft_pred = "FAKE" if x["fft"] >= 0.5 else "REAL"
    cnn_pred = "FAKE" if x["cnn"] >= 0.5 else "REAL"
    fusion_pred = x["final"]

    if fft_pred == gt:
        fft_correct += 1
    else:
        if gt == "REAL":
            fft_fp += 1
        else:
            fft_fn += 1

    if cnn_pred == gt:
        cnn_correct += 1

    if fusion_pred == gt:
        fusion_correct += 1

n = len(data)

print("Total samples:", n)
print("FFT accuracy   :", fft_correct / n)
print("CNN accuracy   :", cnn_correct / n)
print("Fusion accuracy:", fusion_correct / n)

print("FFT false positives:", fft_fp)
print("FFT false negatives:", fft_fn)