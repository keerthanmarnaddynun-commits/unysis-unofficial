from PIL import Image
import os

input_folder = "test_fake_images"
for file in os.listdir(input_folder)[:5]:
    img = Image.open(os.path.join(input_folder, file)).convert("L")
    img.save(os.path.join(input_folder, "gray_" + file))