import os
import warnings
import cv2
from PIL import Image
from torch.utils.data import Dataset
import torchvision.transforms as transforms
import config
from utils import parse_metadata

class DFDCDataset(Dataset):
    def __init__(self, data_dir, metadata_dict, transform=None):
        """
        data_dir: directory containing processed face images
        metadata_dict: dictionary mapping video name to label
        """
        self.data_dir = data_dir
        self.image_files = [f for f in os.listdir(data_dir) if f.endswith('.jpg')]
        self.metadata_dict = metadata_dict
        self.transform = transform
        
        # Filter images that have labels in metadata
        self.valid_images = []
        self.labels = []
        
        for img_file in self.image_files:
            # Assumes img_file format: video_name_frame_0.jpg
            video_key = None
            for key in self.metadata_dict.keys():
                base_key = os.path.splitext(key)[0]
                if img_file.startswith(base_key + "_frame"):
                    video_key = key
                    break
            
            if video_key is not None:
                self.valid_images.append(img_file)
                self.labels.append(self.metadata_dict[video_key])

    def __len__(self):
        return len(self.valid_images)

    def __getitem__(self, idx):
        img_name = self.valid_images[idx]
        img_path = os.path.join(self.data_dir, img_name)
        
        image = Image.open(img_path).convert('RGB')
        label = self.labels[idx]
        
        if self.transform:
            image = self.transform(image)
            
        return image, label


class FolderBinaryDataset(Dataset):
    """
    Dataset for split directories with:
      split_dir/real/*
      split_dir/fake/*
    Label mapping is fixed: real -> 0, fake -> 1
    """

    def __init__(self, split_dir, transform=None, samples=None, labels=None, fake_augment=False):
        self.split_dir = split_dir
        self.transform = transform
        self.fake_augment = fake_augment
        self.class_to_label = {"real": 0, "fake": 1}
        self.allowed_exts = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".jpg", ".jpeg", ".png"}
        self.samples = [] if samples is None else list(samples)
        self.labels = [] if labels is None else list(labels)
        self.fake_only_transform = transforms.Compose([
            transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15, hue=0.02),
            transforms.RandomAffine(degrees=8, translate=(0.03, 0.03), scale=(0.95, 1.05)),
        ])

        if samples is not None and labels is not None:
            return

        for class_name, label in self.class_to_label.items():
            class_dir = os.path.join(split_dir, class_name)
            if not os.path.isdir(class_dir):
                warnings.warn(f"Missing class directory: {class_dir}")
                continue

            files = [
                os.path.join(class_dir, f)
                for f in os.listdir(class_dir)
                if os.path.splitext(f)[1].lower() in self.allowed_exts
            ]
            if len(files) == 0:
                warnings.warn(f"Empty class directory: {class_dir}")

            for path in files:
                self.samples.append(path)
                self.labels.append(label)

    def __len__(self):
        return len(self.samples)

    def _load_item(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in {".jpg", ".jpeg", ".png"}:
            return Image.open(path).convert("RGB")

        cap = cv2.VideoCapture(path)
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            raise ValueError(f"Could not read first frame from video: {path}")
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(frame)

    def __getitem__(self, idx):
        path = self.samples[idx]
        label = self.labels[idx]
        image = self._load_item(path)

        if self.fake_augment and label == 1:
            image = self.fake_only_transform(image)

        if self.transform:
            image = self.transform(image)

        return image, label


def get_transforms():
    """
    Returns standard ImageNet transforms.
    """
    train_transform = transforms.Compose([
        transforms.Resize(config.IMAGE_SIZE),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize(config.IMAGE_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    return train_transform, val_transform
