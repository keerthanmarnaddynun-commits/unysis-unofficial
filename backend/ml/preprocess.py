from typing import Union

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import transforms

from .config import IMAGENET_MEAN, IMAGENET_STD, IMAGE_SIZE


_INFER_TRANSFORM = transforms.Compose(
    [
        transforms.Resize(IMAGE_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ]
)


def to_pil_image(image: Union[Image.Image, np.ndarray]) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")

    if isinstance(image, np.ndarray):
        if image.ndim == 2:
            return Image.fromarray(image).convert("RGB")
        if image.ndim == 3:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return Image.fromarray(rgb).convert("RGB")
        raise ValueError("Unsupported numpy image shape.")

    raise TypeError("Unsupported image type. Expected PIL.Image or OpenCV numpy array.")


def preprocess_image(image: Union[Image.Image, np.ndarray]) -> torch.Tensor:
    pil_image = to_pil_image(image)
    tensor = _INFER_TRANSFORM(pil_image).unsqueeze(0)
    return tensor

