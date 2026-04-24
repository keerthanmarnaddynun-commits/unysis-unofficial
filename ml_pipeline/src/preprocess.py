import os
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

def get_transforms():
    """
    Returns standard ImageNet transforms.
    """
    train_transform = transforms.Compose([
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    val_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    return train_transform, val_transform
