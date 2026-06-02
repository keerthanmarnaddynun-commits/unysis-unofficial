import json

with open(r"D:\forsen\eval_results_original.json") as f:
    orig = json.load(f)

with open(r"D:\forsen\eval_results_jpeg95.json") as f:
    jpg = json.load(f)

orig_map = {x["image"]: x for x in orig}
jpg_map = {x["image"]: x for x in jpg}

improved = []
worsened = []

for img in orig_map:
    o = orig_map[img]
    j = jpg_map[img]

    gt = o["gt"]

    o_pred = "FAKE" if o["fft"] >= 0.5 else "REAL"
    j_pred = "FAKE" if j["fft"] >= 0.5 else "REAL"

    o_ok = (o_pred == gt)
    j_ok = (j_pred == gt)

    if not o_ok and j_ok:
        improved.append((img, o["fft"], j["fft"], gt))

    if o_ok and not j_ok:
        worsened.append((img, o["fft"], j["fft"], gt))

print("\n=== IMPROVED ===")
for x in improved:
    print(x)

print("\n=== WORSENED ===")
for x in worsened:
    print(x)

print("\nImproved:", len(improved))
print("Worsened:", len(worsened))