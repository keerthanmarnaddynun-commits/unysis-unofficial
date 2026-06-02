from PIL import Image
import numpy as np

a = np.array(
    Image.open(r"D:\forsen\debug_runtime_face_crop.png").convert("RGB")
)

b = np.array(
    Image.open(
        r"D:\forsen\final_dataset_aligned\fake\gan_fake_3761_e2c35cfbd0.jpg"
    ).convert("RGB")
)

print("A shape:", a.shape)
print("B shape:", b.shape)

diff = np.abs(a.astype(np.float32) - b.astype(np.float32))

print("Mean abs diff:", diff.mean())
print("Max abs diff :", diff.max())
print("Pixels different:", np.count_nonzero(diff))