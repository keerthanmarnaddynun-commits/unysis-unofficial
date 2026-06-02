"""
AASIST-style audio deepfake detection training script for ASVspoof 2021 DF.

IMPORTANT NOTE:
This implements an AASIST-style architecture (Sinc-based frontend, 1D ResBlocks, 
and Self-Attention pooling). It is NOT the official AASIST or AASIST3 model from 
the original authors, but a lightweight architectural approximation designed to 
fit comfortably on hardware like an RTX 3070.

Example sanity run:
D:\envs\gpu_env\python.exe D:\forsen\train_aasist_audio.py --data_dir <DF_chunk1_path> --max_samples 2000 --epochs 2 --batch_size 8
"""

import os
import sys
import argparse
import logging
import random
import io
import csv
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import torchaudio

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve, roc_auc_score
from sklearn.model_selection import StratifiedShuffleSplit, GroupShuffleSplit

# -----------------------------------------------------------------------------
# AASIST-Style Lightweight Architecture
# -----------------------------------------------------------------------------

class SincConvFast(nn.Module):
    """Simplified 1D Conv frontend."""
    def __init__(self, out_channels, kernel_size, in_channels=1):
        super().__init__()
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, stride=1, padding=kernel_size//2, bias=False)
        self.bn = nn.BatchNorm1d(out_channels)
        self.act = nn.LeakyReLU(0.3)
        self.max_pool = nn.MaxPool1d(3)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.act(x)
        x = self.max_pool(x)
        return x

class ResBlock1D(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, out_channels, 3, padding=1)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.act = nn.LeakyReLU(0.3)
        self.conv2 = nn.Conv1d(out_channels, out_channels, 3, padding=1)
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.max_pool = nn.MaxPool1d(3)
        
        self.shortcut = nn.Sequential()
        if in_channels != out_channels:
            self.shortcut = nn.Conv1d(in_channels, out_channels, 1)

    def forward(self, x):
        res = self.shortcut(x)
        x = self.act(self.bn1(self.conv1(x)))
        x = self.bn2(self.conv2(x))
        x = x + res
        x = self.act(x)
        x = self.max_pool(x)
        return x

class AASISTStyleModel(nn.Module):
    """
    Lightweight AASIST-style architecture.
    Frontend -> 1D ResBlocks -> Self-Attention -> Attentive Pooling -> Classifier.
    """
    def __init__(self, input_len=64000):
        super().__init__()
        self.frontend = SincConvFast(64, 129)
        
        self.res1 = ResBlock1D(64, 64)
        self.res2 = ResBlock1D(64, 128)
        self.res3 = ResBlock1D(128, 128)
        self.res4 = ResBlock1D(128, 256)
        
        self.attn = nn.MultiheadAttention(embed_dim=256, num_heads=4, batch_first=True)
        self.pool_proj = nn.Linear(256, 1)
        
        self.fc1 = nn.Linear(256, 64)
        self.out = nn.Linear(64, 2)

    def forward(self, x):
        x = x.unsqueeze(1) # (B, 1, length)
        x = self.frontend(x)
        x = self.res1(x)
        x = self.res2(x)
        x = self.res3(x)
        x = self.res4(x) # (B, 256, L)
        
        x = x.transpose(1, 2) # (B, L, 256)
        x_attn, _ = self.attn(x, x, x)
        x = x + x_attn
        
        w = torch.softmax(self.pool_proj(x), dim=1) # (B, L, 1)
        x = torch.sum(x * w, dim=1) # (B, 256)
        
        x = F.leaky_relu(self.fc1(x), 0.3)
        logits = self.out(x)
        return logits

# -----------------------------------------------------------------------------
# EMA
# -----------------------------------------------------------------------------

class EMA:
    def __init__(self, model, decay):
        self.decay = decay
        self.shadow = {}
        self.backup = {}
        for name, param in model.named_parameters():
            if param.requires_grad:
                self.shadow[name] = param.data.clone()

    def update(self, model):
        for name, param in model.named_parameters():
            if param.requires_grad:
                self.shadow[name] -= (1.0 - self.decay) * (self.shadow[name] - param.data)

    def apply_shadow(self, model):
        for name, param in model.named_parameters():
            if param.requires_grad:
                self.backup[name] = param.data.clone()
                param.data.copy_(self.shadow[name])

    def restore(self, model):
        for name, param in model.named_parameters():
            if param.requires_grad:
                if name in self.backup:
                    param.data.copy_(self.backup[name])
        self.backup = {}

    def get_state(self):
        return {k: v.clone() for k, v in self.shadow.items()}

    def load_state(self, state):
        self.shadow = {k: v.clone() for k, v in state.items()}

# -----------------------------------------------------------------------------
# Data Loader and Augmentation
# -----------------------------------------------------------------------------

def pad_or_crop(waveform, target_len, mode="train"):
    c, length = waveform.shape
    if length < target_len:
        pad_len = target_len - length
        waveform = F.pad(waveform, (0, pad_len), "constant", 0)
    elif length > target_len:
        if mode == "train":
            start = random.randint(0, length - target_len)
        else:
            start = (length - target_len) // 2
        waveform = waveform[:, start:start+target_len]
    return waveform

class AudioAugmentation:
    def __init__(self, sr=16000):
        self.sr = sr
        self.has_pydub = False
        try:
            import pydub
            self.has_pydub = True
        except ImportError:
            logging.warning("pydub not installed. MP3/AAC augmentation will be skipped.")
        
    def add_noise(self, waveform):
        noise = torch.randn_like(waveform)
        snr = random.uniform(10, 30)
        noise_power = waveform.norm(p=2) / (10 ** (snr / 20) + 1e-8)
        return waveform + noise * noise_power * 0.1

    def bandpass_filter(self, waveform):
        return torchaudio.functional.bandpass_biquad(waveform, self.sr, 1850, 2.0)

    def resample_degradation(self, waveform):
        low_sr = random.choice([8000, 11025])
        down = torchaudio.functional.resample(waveform, self.sr, low_sr)
        return torchaudio.functional.resample(down, low_sr, self.sr)

    def _pydub_compression(self, waveform, fmt, codec=None, bitrate="64k"):
        if not self.has_pydub:
            return waveform
        from pydub import AudioSegment
        try:
            audio_np = (waveform.squeeze(0).numpy() * 32767).astype(np.int16)
            segment = AudioSegment(audio_np.tobytes(), frame_rate=self.sr, sample_width=2, channels=1)
            buf = io.BytesIO()
            kwargs = {"format": fmt, "bitrate": bitrate}
            if codec: kwargs["codec"] = codec
            segment.export(buf, **kwargs)
            buf.seek(0)
            seg_compressed = AudioSegment.from_file(buf)
            arr = np.array(seg_compressed.get_array_of_samples(), dtype=np.float32) / 32767.0
            return torch.from_numpy(arr).unsqueeze(0)
        except Exception:
            # Fallback if ffmpeg isn't reachable by pydub
            return waveform
            
    def apply_mp3(self, waveform):
        return self._pydub_compression(waveform, fmt="mp3", bitrate=random.choice(["32k", "64k", "128k"]))

    def apply_aac(self, waveform):
        return self._pydub_compression(waveform, fmt="adts", codec="aac", bitrate=random.choice(["32k", "64k"]))

    def __call__(self, waveform):
        if random.random() < 0.3:
            waveform = self.add_noise(waveform)
        if random.random() < 0.3:
            waveform = self.bandpass_filter(waveform)
        if random.random() < 0.3:
            waveform = self.resample_degradation(waveform)
        if self.has_pydub and random.random() < 0.3:
            if random.random() < 0.5:
                waveform = self.apply_mp3(waveform)
            else:
                waveform = self.apply_aac(waveform)
        return waveform

class ASVSpoofDataset(Dataset):
    def __init__(self, manifest_df, target_sr=16000, target_len=64000, mode="train"):
        self.df = manifest_df
        self.target_sr = target_sr
        self.target_len = target_len
        self.mode = mode
        self.aug = AudioAugmentation(target_sr) if mode == "train" else None

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        audio_path = row['path']
        label = row['label'] 
        
        try:
            waveform, sr = torchaudio.load(audio_path)
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
                
            if sr != self.target_sr:
                waveform = torchaudio.functional.resample(waveform, sr, self.target_sr)
                
            if self.aug is not None:
                waveform = self.aug(waveform)
                
            waveform = pad_or_crop(waveform, self.target_len, self.mode)
            return waveform.squeeze(0), torch.tensor(label, dtype=torch.long), str(audio_path)
        except Exception:
            return None, str(audio_path)

# -----------------------------------------------------------------------------
# Utils and Metrics
# -----------------------------------------------------------------------------

def compute_eer(y_true, y_score):
    fpr, tpr, thresholds = roc_curve(y_true, y_score, pos_label=1)
    fnr = 1 - tpr
    idx = np.nanargmin(np.absolute(fnr - fpr))
    eer = (fpr[idx] + fnr[idx]) / 2.0
    return eer

def build_manifest(data_dir, keys_dir, max_samples=None):
    logging.info("Building manifest...")
    flac_files = list(Path(data_dir).rglob("*.flac"))
    if not flac_files:
        raise ValueError(f"No FLAC files found in {data_dir}")
        
    logging.info(f"Found {len(flac_files)} FLAC files.")
    
    keys_file = None
    if keys_dir and Path(keys_dir).exists():
        txt_files = list(Path(keys_dir).rglob("*.txt"))
        if txt_files:
            keys_file = txt_files[0]
            
    labels_dict = {}
    speaker_dict = {}
    if keys_file:
        logging.info(f"Using keys from {keys_file}")
        with open(keys_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    spk, fn, _, _, lbl = parts[0], parts[1], parts[2], parts[3], parts[4]
                    labels_dict[fn] = 0 if lbl.lower() == 'bonafide' else 1
                    speaker_dict[fn] = spk
    else:
        logging.warning("No keys_dir provided or keys not found. Defaulting to dummy labels.")
    
    data = []
    for p in flac_files:
        fn = p.stem
        if keys_file and fn not in labels_dict:
            continue
        label = labels_dict.get(fn, 1) 
        spk = speaker_dict.get(fn, "unknown")
        data.append({"path": str(p), "label": label, "speaker": spk, "filename": fn})
        
    df = pd.DataFrame(data)
    if max_samples and max_samples < len(df):
        df = df.sample(n=max_samples, random_state=42).reset_index(drop=True)
    return df

def create_splits(df):
    if df['speaker'].nunique() > 1 and "unknown" not in df['speaker'].values:
        logging.info("Speaker metadata found. Using GroupShuffleSplit for group-aware split.")
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, val_idx = next(gss.split(df, groups=df['speaker']))
        return df.iloc[train_idx].reset_index(drop=True), df.iloc[val_idx].reset_index(drop=True)
    else:
        logging.warning("No speaker metadata. Using StratifiedShuffleSplit.")
        sss = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, val_idx = next(sss.split(df, df['label']))
        return df.iloc[train_idx].reset_index(drop=True), df.iloc[val_idx].reset_index(drop=True)

def get_collate_fn(bad_audio_log):
    def collate_fn(batch):
        valid_batch = []
        bad_files = []
        for b in batch:
            if b[0] is None:
                bad_files.append(b[1])
            else:
                valid_batch.append(b)
                
        if bad_files:
            with open(bad_audio_log, "a") as f:
                for bf in bad_files:
                    f.write(bf + "\n")
                    
        if not valid_batch:
            return torch.empty(0), torch.empty(0), []
            
        waves, labels, paths = zip(*valid_batch)
        return torch.stack(waves), torch.stack(labels), paths
    return collate_fn

# -----------------------------------------------------------------------------
# Training Loop
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, required=True, help="Path to ASVspoof DF audio chunks")
    parser.add_argument("--keys_dir", type=str, default="", help="Path to DF-keys-full metadata")
    parser.add_argument("--max_samples", type=int, default=None, help="Sanity testing limit")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--audio_len", type=int, default=64000, help="Fixed length for audio")
    parser.add_argument("--out_dir", type=str, default="aasist_output")
    parser.add_argument("--num_workers", type=int, default=4, help="Number of Dataloader workers")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(os.path.join(args.out_dir, "train.log"))])

    bad_audio_log = os.path.join(args.out_dir, "bad_audio.txt")

    # Set seeds
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    df = build_manifest(args.data_dir, args.keys_dir, args.max_samples)
    if len(df) == 0:
        logging.error("No valid samples found!")
        return
        
    train_df, val_df = create_splits(df)
    train_csv = os.path.join(args.out_dir, "train_split.csv")
    val_csv = os.path.join(args.out_dir, "val_split.csv")
    train_df.to_csv(train_csv, index=False)
    val_df.to_csv(val_csv, index=False)
    logging.info(f"Saved splits to {train_csv} and {val_csv}")

    # Compute class weights based on train_df
    class_counts = train_df['label'].value_counts()
    total = len(train_df)
    w0 = total / (2.0 * class_counts.get(0, 1))
    w1 = total / (2.0 * class_counts.get(1, 1))
    class_weights = torch.tensor([w0, w1], dtype=torch.float)
    logging.info(f"Class weights (bonafide, spoof): {class_weights}")

    train_dataset = ASVSpoofDataset(train_df, target_len=args.audio_len, mode="train")
    val_dataset = ASVSpoofDataset(val_df, target_len=args.audio_len, mode="val")

    collate = get_collate_fn(bad_audio_log)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers, collate_fn=collate)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers, collate_fn=collate)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AASISTStyleModel(input_len=args.audio_len).to(device)
    ema = EMA(model, decay=0.999)
    
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    
    best_eer = float("inf")
    
    val_scores_file = os.path.join(args.out_dir, "val_scores.csv")
    val_details_file = os.path.join(args.out_dir, "val_details.csv")
    
    with open(val_scores_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Epoch", "Val_Loss", "Val_Acc", "Val_EER", "Val_AUC"])
        
    with open(val_details_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["epoch", "path", "label", "score"])

    logging.info("Starting training...")
    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0
        for waves, labels, _ in train_loader:
            if len(waves) == 0: continue
            waves, labels = waves.to(device), labels.to(device)
            optimizer.zero_grad()
            logits = model(waves)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            ema.update(model)
            train_loss += loss.item() * waves.size(0)
            
        train_loss /= max(len(train_dataset), 1)
        
        # Eval with EMA model
        model.eval()
        ema.apply_shadow(model)
        
        val_loss = 0
        correct = 0
        all_labels = []
        all_scores = []
        all_paths = []
        
        with torch.no_grad():
            for waves, labels, paths in val_loader:
                if len(waves) == 0: continue
                waves, labels = waves.to(device), labels.to(device)
                logits = model(waves)
                loss = criterion(logits, labels)
                val_loss += loss.item() * waves.size(0)
                
                probs = torch.softmax(logits, dim=1)[:, 1]
                preds = torch.argmax(logits, dim=1)
                
                correct += (preds == labels).sum().item()
                all_labels.extend(labels.cpu().numpy())
                all_scores.extend(probs.cpu().numpy())
                all_paths.extend(paths)
                
        val_loss /= max(len(val_dataset), 1)
        val_acc = correct / max(len(val_dataset), 1)
        
        if len(set(all_labels)) > 1:
            eer = compute_eer(all_labels, all_scores)
            auc = roc_auc_score(all_labels, all_scores)
        else:
            eer, auc = 1.0, 0.0
            
        # Write validation details for this epoch
        with open(val_details_file, "a", newline="") as f:
            writer = csv.writer(f)
            for p, l, s in zip(all_paths, all_labels, all_scores):
                writer.writerow([epoch, p, l, s])
            
        if eer < best_eer:
            best_eer = eer
            
            # Extract EMA model dict as primary since shadow is currently applied
            ema_state_dict = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            
            # Restore normal weights
            ema.restore(model)
            normal_state_dict = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            
            rng_state_cuda = torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None
            
            ckpt = {
                "epoch": epoch,
                "model_state_dict": ema_state_dict,
                "normal_model_state_dict": normal_state_dict,
                "optimizer_state_dict": optimizer.state_dict(),
                "scheduler_state_dict": scheduler.state_dict(),
                "ema_state": ema.get_state(),
                "rng_state_torch": torch.get_rng_state(),
                "rng_state_cuda": rng_state_cuda,
                "rng_state_np": np.random.get_state(),
                "rng_state_random": random.getstate(),
                "class_weights": class_weights,
                "train_split": train_csv,
                "val_split": val_csv,
                "config": vars(args),
                "best_val_eer": best_eer,
                "val_accuracy": val_acc
            }
            torch.save(ckpt, os.path.join(args.out_dir, "best_model.pth"))
            logging.info(f"--> Saved new best model with EER: {best_eer:.4f}")
        else:
            # Restore normal weights to continue training if no new best
            ema.restore(model)
            
        scheduler.step()
        
        logging.info(f"Epoch {epoch:03d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f} | EER: {eer:.4f} | AUC: {auc:.4f}")
        
        with open(val_scores_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([epoch, val_loss, val_acc, eer, auc])

if __name__ == "__main__":
    main()
