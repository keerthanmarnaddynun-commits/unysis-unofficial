import os
import warnings
import torch
from torch.utils.data import DataLoader, random_split
import config
from preprocess import FolderBinaryDataset, get_transforms


def _validate_split_dir(split_dir):
    if not os.path.isdir(split_dir):
        raise FileNotFoundError(f"Dataset split directory not found: {split_dir}")

    for class_name in ("real", "fake"):
        class_dir = os.path.join(split_dir, class_name)
        if not os.path.isdir(class_dir):
            raise FileNotFoundError(f"Class directory not found: {class_dir}")


def get_data_loaders(train_dir=None, val_dir=None, test_dir=None):
    """
    Creates DataLoaders for train/val/test split directories:
      split/real, split/fake
    """
    train_dir = train_dir or config.TRAIN_DIR
    val_dir = val_dir or config.VAL_DIR
    test_dir = test_dir or config.TEST_DIR

    _validate_split_dir(train_dir)
    _validate_split_dir(test_dir)

    train_transform, val_transform = get_transforms()
    full_train_dataset = FolderBinaryDataset(train_dir, transform=None)
    test_dataset = FolderBinaryDataset(test_dir, transform=val_transform)

    if os.path.isdir(val_dir):
        _validate_split_dir(val_dir)
        train_dataset = FolderBinaryDataset(train_dir, transform=train_transform, fake_augment=True)
        val_dataset = FolderBinaryDataset(val_dir, transform=val_transform)
    else:
        warnings.warn(
            f"Validation split not found at {val_dir}. Splitting {config.VAL_SPLIT_RATIO:.0%} from train."
        )
        train_size = int((1.0 - config.VAL_SPLIT_RATIO) * len(full_train_dataset))
        val_size = len(full_train_dataset) - train_size
        if val_size == 0 and len(full_train_dataset) > 1:
            val_size = 1
            train_size = len(full_train_dataset) - 1
        train_subset, val_subset = random_split(
            full_train_dataset,
            [train_size, val_size],
            generator=torch.Generator().manual_seed(config.RANDOM_SEED),
        )

        train_samples = [full_train_dataset.samples[i] for i in train_subset.indices]
        train_labels_local = [full_train_dataset.labels[i] for i in train_subset.indices]
        val_samples = [full_train_dataset.samples[i] for i in val_subset.indices]
        val_labels_local = [full_train_dataset.labels[i] for i in val_subset.indices]

        train_dataset = FolderBinaryDataset(
            train_dir,
            transform=train_transform,
            samples=train_samples,
            labels=train_labels_local,
            fake_augment=True,
        )
        val_dataset = FolderBinaryDataset(
            train_dir,
            transform=val_transform,
            samples=val_samples,
            labels=val_labels_local,
        )

    if len(train_dataset) == 0:
        raise ValueError(f"Train split is empty: {train_dir}")
    if len(val_dataset) == 0:
        warnings.warn(f"Validation split is empty: {val_dir}")
    if len(test_dataset) == 0:
        warnings.warn(f"Test split is empty: {test_dir}")

    train_loader = DataLoader(train_dataset, batch_size=config.BATCH_SIZE, shuffle=True, num_workers=4, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=config.BATCH_SIZE, shuffle=False, num_workers=4, pin_memory=True)
    test_loader = DataLoader(test_dataset, batch_size=config.BATCH_SIZE, shuffle=False, num_workers=4, pin_memory=True)

    train_labels = train_dataset.labels
    split_sizes = {
        "train": len(train_dataset),
        "val": len(val_dataset),
        "test": len(test_dataset),
    }
    class_counts = {
        "train": {
            "real": train_dataset.labels.count(0),
            "fake": train_dataset.labels.count(1),
        },
        "val": {
            "real": val_dataset.labels.count(0),
            "fake": val_dataset.labels.count(1),
        },
        "test": {
            "real": test_dataset.labels.count(0),
            "fake": test_dataset.labels.count(1),
        },
    }

    return train_loader, val_loader, test_loader, train_labels, split_sizes, class_counts
