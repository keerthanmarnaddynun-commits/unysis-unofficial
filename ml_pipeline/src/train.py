import os
import argparse
import warnings
import torch
import torch.nn as nn
import torch.optim as optim
from tqdm import tqdm
from sklearn.metrics import confusion_matrix
import config
from utils import setup_logger, save_checkpoint, calculate_class_weights
from data_loader import get_data_loaders
from model import DeepfakeClassifier
from evaluate import compute_metrics

def train(debug_mode=False):
    logger = setup_logger('train_logger', os.path.join(config.BASE_DIR, 'training.log'))
    logger.info("Starting training pipeline...")
    
    # 1. Load Data
    try:
        train_loader, val_loader, test_loader, train_labels, split_sizes, class_counts = get_data_loaders()
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Data Loader Error: {str(e)}")
        return

    print(f"Dataset root: {config.DATASET_BASE_DIR}")
    print(
        "Train summary -> real: {real}, fake: {fake}".format(
            real=class_counts["train"]["real"], fake=class_counts["train"]["fake"]
        )
    )
    print(
        "Test summary  -> real: {real}, fake: {fake}".format(
            real=class_counts["test"]["real"], fake=class_counts["test"]["fake"]
        )
    )
    print(
        "Val summary   -> real: {real}, fake: {fake}".format(
            real=class_counts["val"]["real"], fake=class_counts["val"]["fake"]
        )
    )
    train_total = max(class_counts["train"]["real"] + class_counts["train"]["fake"], 1)
    train_fake_ratio = class_counts["train"]["fake"] / train_total
    print(f"Class balance check (train fake ratio): {train_fake_ratio:.3f}")

    logger.info(
        "Loaded dataset sizes - train: %d, val: %d, test: %d",
        split_sizes["train"],
        split_sizes["val"],
        split_sizes["test"],
    ) 
    if split_sizes["val"] == 0:
        warnings.warn("Validation split is empty.")
    if split_sizes["test"] == 0:
        warnings.warn("Test split is empty.")
    
    # 2. Compute Class Weights
    class_weights = calculate_class_weights(train_labels).to(config.DEVICE)
    logger.info(f"Computed class weights: {class_weights}")
    
    # 3. Initialize Model, Loss, Optimizer
    model = DeepfakeClassifier(pretrained=True).to(config.DEVICE)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = optim.Adam(model.parameters(), lr=config.LEARNING_RATE)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=2
    )
    
    best_val_accuracy = 0.0
    
    # 4. Training Loop
    epochs = 1 if debug_mode else config.NUM_EPOCHS
    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        train_correct = 0
        train_total_seen = 0
        
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
            _, preds = torch.max(outputs, 1)
            train_correct += (preds == labels).sum().item()
            train_total_seen += labels.size(0)
            train_bar.set_postfix(loss=loss.item())
            
        epoch_loss = running_loss / max(len(train_loader), 1)
        train_accuracy = train_correct / max(train_total_seen, 1)
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
        logger.info(
            "Epoch %d - Accuracy train: %.4f | val: %.4f",
            epoch,
            train_accuracy,
            metrics["accuracy"],
        )
        print(
            f"Epoch {epoch}: train_acc={train_accuracy:.4f}, val_acc={metrics['accuracy']:.4f}, val_loss={val_loss:.4f}"
        )
        scheduler.step(val_loss)
        
        # 6. Checkpointing
        is_best = metrics['accuracy'] > best_val_accuracy
        if is_best:
            best_val_accuracy = metrics['accuracy']
            logger.info(f"New best validation accuracy: {best_val_accuracy:.4f}")
            
        save_checkpoint(model, optimizer, epoch, is_best, config.CHECKPOINT_DIR)

    # 7. Optional test-set evaluation with final model state
    if len(test_loader.dataset) > 0:
        model.eval()
        test_preds = []
        test_labels = []
        with torch.no_grad():
            for images, labels in tqdm(test_loader, desc="Final [Test]"):
                images = images.to(config.DEVICE)
                outputs = model(images)
                _, preds = torch.max(outputs, 1)
                test_preds.extend(preds.cpu().numpy())
                test_labels.extend(labels.numpy())

        test_metrics = compute_metrics(test_labels, test_preds)
        logger.info(f"Final Test Metrics: {test_metrics}")
        cm = confusion_matrix(test_labels, test_preds, labels=[0, 1])
        pred_real = sum(1 for p in test_preds if p == 0)
        pred_fake = sum(1 for p in test_preds if p == 1)
        print(f"Test Accuracy: {test_metrics['accuracy']:.4f}")
        print(f"Confusion Matrix [[TN, FP], [FN, TP]]: {cm.tolist()}")
        print(f"Prediction counts -> real: {pred_real}, fake: {pred_fake}")

        # Sanity inference on a few raw test samples
        sample_count = min(3, len(test_loader.dataset))
        print("Sample test predictions:")
        for idx in range(sample_count):
            image, true_label = test_loader.dataset[idx]
            with torch.no_grad():
                output = model(image.unsqueeze(0).to(config.DEVICE))
                pred = int(torch.argmax(output, dim=1).item())
            sample_path = os.path.basename(test_loader.dataset.samples[idx])
            print(f"  {sample_path}: true={true_label}, pred={pred}")
    else:
        logger.warning("Skipping test evaluation because test split is empty.")

    model_output_path = os.path.join(config.BASE_DIR, "models", "model.pth")
    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    torch.save(model.state_dict(), model_output_path)
    logger.info(f"Saved final model to {model_output_path}")
    print(f"Saved model: {model_output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deepfake Detection Training Pipeline")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode (1 epoch, limited batches)")
    args = parser.parse_args()
    
    train(debug_mode=args.debug)
