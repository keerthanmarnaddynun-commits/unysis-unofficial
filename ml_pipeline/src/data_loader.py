import os
from torch.utils.data import DataLoader, random_split
import config
from utils import parse_metadata
from preprocess import DFDCDataset, get_transforms

def get_data_loaders(metadata_path, test_split=0.2):
    """
    Creates DataLoaders for training and validation.
    """
    metadata_dict = parse_metadata(metadata_path)
    train_transform, val_transform = get_transforms()
    
    # Create full dataset
    full_dataset = DFDCDataset(config.PROCESSED_DATA_DIR, metadata_dict, transform=val_transform)
    
    dataset_size = len(full_dataset)
    if dataset_size == 0:
        raise ValueError("No matching images and metadata found. Please check data/processed and data/metadata.")
        
    val_size = int(test_split * dataset_size)
    train_size = dataset_size - val_size
    
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])
    
    # Create loaders
    train_loader = DataLoader(train_dataset, batch_size=config.BATCH_SIZE, shuffle=True, num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=config.BATCH_SIZE, shuffle=False, num_workers=4, pin_memory=True)
    
    # Overwrite transform for train dataset after split
    # random_split wraps dataset in Subset, so we can't easily change transform
    # The simplest way is to manually apply transforms or re-initialize.
    # For a robust pipeline, it's better to pass transform in __getitem__ 
    # but since it's already implemented, we'll keep it simple: 
    # A cleaner approach is passing transform logic into DFDCDataset or 
    # overriding the wrapper. For now, since both use ToTensor and Normalize, 
    # it's acceptable. For proper augmentation, we update DFDCDataset logic.
    
    # To fix the random_split transform issue cleanly:
    train_dataset.dataset.transform = train_transform
    
    # Extract labels for class weights
    train_labels = [full_dataset.labels[i] for i in train_dataset.indices]
    
    return train_loader, val_loader, train_labels
