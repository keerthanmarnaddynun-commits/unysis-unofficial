import os
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from tqdm import tqdm
import config
from utils import setup_logger, save_checkpoint, calculate_class_weights
from data_loader import get_data_loaders
from model import DeepfakeClassifier
from evaluate import compute_metrics

def train(debug_mode=False):
    logger = setup_logger('train_logger', os.path.join(config.BASE_DIR, 'training.log'))
    logger.info("Starting training pipeline...")
    
    # 1. Load Data
    metadata_path = None
    for file in os.listdir(config.METADATA_DIR):
        if file.endswith(('.json', '.csv')):
            metadata_path = os.path.join(config.METADATA_DIR, file)
            break
            
    if not metadata_path:
        logger.error("No metadata file found in data/metadata/")
        return
        
    try:
        train_loader, val_loader, train_labels = get_data_loaders(metadata_path)
    except ValueError as e:
        logger.error(f"Data Loader Error: {str(e)}")
        return
        
    logger.info(f"Loaded {len(train_loader.dataset)} training samples and {len(val_loader.dataset)} validation samples.")
    
    # 2. Compute Class Weights
    class_weights = calculate_class_weights(train_labels).to(config.DEVICE)
    logger.info(f"Computed class weights: {class_weights}")
    
    # 3. Initialize Model, Loss, Optimizer
    model = DeepfakeClassifier(pretrained=True).to(config.DEVICE)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = optim.Adam(model.parameters(), lr=config.LEARNING_RATE)
    
    best_val_accuracy = 0.0
    
    # 4. Training Loop
    epochs = 1 if debug_mode else config.NUM_EPOCHS
    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        
        train_bar = tqdm(train_loader, desc=f"Epoch {epoch}/{epochs} [Train]")
        for i, (images, labels) in enumerate(train_bar):
            if debug_mode and i >= 2:
                break
                
            images, labels = images.to(config.DEVICE), labels.to(config.DEVICE)
            
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            train_bar.set_postfix(loss=loss.item())
            
        epoch_loss = running_loss / max(len(train_loader), 1)
        logger.info(f"Epoch {epoch} - Training Loss: {epoch_loss:.4f}")
        
        # 5. Validation Loop
        model.eval()
        all_preds = []
        all_labels = []
        val_loss = 0.0
        
        val_bar = tqdm(val_loader, desc=f"Epoch {epoch}/{epochs} [Val]")
        with torch.no_grad():
            for i, (images, labels) in enumerate(val_bar):
                if debug_mode and i >= 2:
                    break
                    
                images, labels = images.to(config.DEVICE), labels.to(config.DEVICE)
                
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss += loss.item()
                
                _, preds = torch.max(outputs, 1)
                
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
                
        val_loss /= max(len(val_loader), 1)
        
        if len(all_labels) > 0:
            metrics = compute_metrics(all_labels, all_preds)
        else:
            metrics = {'accuracy': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1': 0.0}
        
        logger.info(f"Epoch {epoch} - Validation Loss: {val_loss:.4f}")
        logger.info(f"Epoch {epoch} - Metrics: {metrics}")
        
        # 6. Checkpointing
        is_best = metrics['accuracy'] > best_val_accuracy
        if is_best:
            best_val_accuracy = metrics['accuracy']
            logger.info(f"New best validation accuracy: {best_val_accuracy:.4f}")
            
        save_checkpoint(model, optimizer, epoch, is_best, config.CHECKPOINT_DIR)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deepfake Detection Training Pipeline")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode (1 epoch, limited batches)")
    args = parser.parse_args()
    
    train(debug_mode=args.debug)
