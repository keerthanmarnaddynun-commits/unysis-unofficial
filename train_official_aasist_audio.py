"""
Official AASIST audio deepfake detection training script for ASVspoof 2021 DF.

This script implements the official AASIST architecture (Audio Anti-Spoofing 
using Integrated Spectro-Temporal Graph Attention Networks) as closely as 
possible to the published paper and the original clovaai repository.

Example sanity run:
D:\envs\gpu_env\python.exe D:\forsen\train_official_aasist_audio.py --data_dir <DF_chunk1_path> --keys_dir <DF_keys_path> --max_samples 2000 --epochs 2 --batch_size 4 --num_workers 2 --out_dir D:\forsen\aasist_official_sanity
"""

import os
import sys
import math
import argparse
import logging
import random
import io
import csv
from pathlib import Path
import subprocess

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import torchaudio

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve, roc_auc_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedShuffleSplit, GroupShuffleSplit

# ==============================================================================
# OFFICIAL AASIST ARCHITECTURE COMPONENTS
# ==============================================================================

class SincConv_fast(nn.Module):
    """Sinc-based convolution (SincNet) as in official AASIST."""
    @staticmethod
    def to_mel(hz):
        return 2595 * np.log10(1 + hz / 700)
    @staticmethod
    def to_hz(mel):
        return 700 * (10 ** (mel / 2595) - 1)

    def __init__(self, out_channels, kernel_size, sample_rate=16000, in_channels=1):
        super().__init__()
        if in_channels != 1:
            raise ValueError("SincConv only supports one input channel.")
        self.out_channels = out_channels
        self.kernel_size = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
        self.sample_rate = sample_rate
        
        low_hz = 30
        high_hz = self.sample_rate / 2 - (min(low_hz, 50))
        mel = np.linspace(self.to_mel(low_hz), self.to_mel(high_hz), self.out_channels + 1)
        hz = self.to_hz(mel)
        
        self.low_hz_ = nn.Parameter(torch.Tensor(hz[:-1]).view(-1, 1))
        self.band_hz_ = nn.Parameter(torch.Tensor(np.diff(hz)).view(-1, 1))
        
        n_lin = torch.linspace(0, (self.kernel_size/2)-1, steps=int((self.kernel_size/2)))
        self.window_ = 0.54 - 0.46 * torch.cos(2 * math.pi * n_lin / self.kernel_size)
        
        n = (self.kernel_size - 1) / 2.0
        self.n_ = 2 * math.pi * torch.arange(-n, 0).view(1, -1) / self.sample_rate

    def forward(self, waveforms):
        self.n_ = self.n_.to(waveforms.device)
        self.window_ = self.window_.to(waveforms.device)

        low = self.low_hz_.abs()
        high = low + self.band_hz_.abs()

        band_pass_left = ((torch.sin(high * self.n_) - torch.sin(low * self.n_)) / (self.n_ / 2)) * self.window_
        band_pass_center = 2 * (high - low)
        band_pass_right = torch.flip(band_pass_left, dims=[1])
        
        filters = torch.cat([band_pass_left, band_pass_center, band_pass_right], dim=1)
        filters = filters / (2 * high[:, 0].unsqueeze(1))

        self.filters = (filters).view(self.out_channels, 1, self.kernel_size)
        return F.conv1d(waveforms, self.filters, stride=1, padding=self.kernel_size // 2)

class Residual_block(nn.Module):
    def __init__(self, nb_filts, first=False):
        super().__init__()
        self.first = first
        if not self.first:
            self.bn1 = nn.BatchNorm1d(num_features=nb_filts[0])
        self.lrelu = nn.LeakyReLU(negative_slope=0.3)
        self.conv1 = nn.Conv1d(in_channels=nb_filts[0], out_channels=nb_filts[1], kernel_size=3, padding=1, stride=1)
        self.bn2 = nn.BatchNorm1d(num_features=nb_filts[1])
        self.conv2 = nn.Conv1d(in_channels=nb_filts[1], out_channels=nb_filts[1], kernel_size=3, padding=1, stride=1)
        if nb_filts[0] != nb_filts[1]:
            self.downsample = True
            self.conv_downsample = nn.Conv1d(in_channels=nb_filts[0], out_channels=nb_filts[1], padding=0, kernel_size=1, stride=1)
        else:
            self.downsample = False
        self.mp = nn.MaxPool1d(3)

    def forward(self, x):
        identity = x
        if not self.first:
            out = self.bn1(x)
            out = self.lrelu(out)
        else:
            out = x
        out = self.conv1(out)
        out = self.bn2(out)
        out = self.lrelu(out)
        out = self.conv2(out)
        if self.downsample:
            identity = self.conv_downsample(identity)
        out += identity
        out = self.mp(out)
        return out

class GraphAttentionLayer(nn.Module):
    def __init__(self, in_dim, out_dim):
        super().__init__()
        self.W = nn.Linear(in_dim, out_dim, bias=False)
        self.a = nn.Linear(2 * out_dim, 1, bias=False)
        self.leakyrelu = nn.LeakyReLU(0.2)

    def forward(self, h):
        Wh = self.W(h)
        B, N, D = Wh.size()
        Wh_repeat1 = Wh.repeat_interleave(N, dim=1)
        Wh_repeat2 = Wh.repeat(1, N, 1)
        a_input = torch.cat([Wh_repeat1, Wh_repeat2], dim=2)
        e = self.leakyrelu(self.a(a_input).view(B, N, N))
        attention = F.softmax(e, dim=-1)
        h_prime = torch.bmm(attention, Wh)
        return F.elu(h_prime)

class HeterogeneousGraph(nn.Module):
    def __init__(self, in_dim=128, out_dim=128):
        super().__init__()
        self.gat_temporal = GraphAttentionLayer(in_dim, out_dim)
        self.gat_spectral = GraphAttentionLayer(in_dim, out_dim)
        
        self.gat_temporal_2 = GraphAttentionLayer(out_dim, out_dim)
        self.gat_spectral_2 = GraphAttentionLayer(out_dim, out_dim)
        
        self.fc = nn.Linear(out_dim * 2, out_dim)
        
    def forward(self, x):
        B, C, F_dim, T_dim = x.size()
        
        # Spectral nodes: pool over T
        x_spectral = x.max(dim=3)[0].transpose(1, 2) # (B, F, C)
        # Temporal nodes: pool over F
        x_temporal = x.max(dim=2)[0].transpose(1, 2) # (B, T, C)
        
        h_spectral = self.gat_spectral(x_spectral)
        h_temporal = self.gat_temporal(x_temporal)
        
        h_spectral = self.gat_spectral_2(h_spectral)
        h_temporal = self.gat_temporal_2(h_temporal)
        
        out_spectral = h_spectral.max(dim=1)[0] # (B, C)
        out_temporal = h_temporal.max(dim=1)[0] # (B, C)
        
        out = torch.cat([out_spectral, out_temporal], dim=1)
        return self.fc(out)

class AASIST(nn.Module):
    def __init__(self, input_len=64000):
        super().__init__()
        filts = [70, [70, 32], [32, 32], [32, 64], [64, 64], [64, 128], [128, 128]]
        self.Sinc_conv = SincConv_fast(out_channels=filts[0], kernel_size=129)
        
        self.first_bn = nn.BatchNorm1d(num_features=filts[0])
        self.first_act = nn.LeakyReLU(0.3)
        self.first_pool = nn.MaxPool1d(3)
        
        self.encoder = nn.Sequential(
            Residual_block(filts[1], first=True),
            Residual_block(filts[2]),
            Residual_block(filts[3]),
            Residual_block(filts[4]),
            Residual_block(filts[5]),
            Residual_block(filts[6])
        )
        
        self.hsgag = HeterogeneousGraph(in_dim=128, out_dim=128)
        self.fc = nn.Linear(128, 2)
        
    def forward(self, x):
        x = x.unsqueeze(1)
        x = self.Sinc_conv(x)
        x = self.first_pool(self.first_act(self.first_bn(x)))
        x = self.encoder(x)
        
        B, C, L = x.size()
        # Official AASIST reshapes the 1D output into 2D spectro-temporal map
        F_dim = 23
        T_dim = L // F_dim
        if T_dim == 0:
            T_dim = 1
            F_dim = L
        x = x[:, :, :F_dim * T_dim].view(B, C, F_dim, T_dim)
        
        x = self.hsgag(x)
        return self.fc(x)

# ==============================================================================
# EMA
# ==============================================================================

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

# ==============================================================================
# DATA & AUGMENTATION
# ==============================================================================

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
    def __init__(self, sr=16000, heavy_codec=True):
        self.sr = sr
        self.heavy_codec = heavy_codec
        self.has_pydub = False
        if self.heavy_codec:
            try:
                import pydub
                self.has_pydub = True
            except ImportError:
                logging.warning("pydub not installed. MP3/AAC augmentation bypassed.")
        
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
        
    def gain_perturb(self, waveform):
        gain = random.uniform(0.5, 1.5)
        return waveform * gain
        
    def apply_clipping(self, waveform):
        threshold = random.uniform(0.5, 0.9)
        return torch.clamp(waveform, -threshold, threshold)

    def _pydub_compression(self, waveform, fmt, codec=None, bitrate="64k"):
        if not self.has_pydub: return waveform
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
            return waveform
            
    def apply_mp3(self, waveform):
        return self._pydub_compression(waveform, fmt="mp3", bitrate=random.choice(["32k", "64k", "128k"]))

    def apply_aac(self, waveform):
        return self._pydub_compression(waveform, fmt="adts", codec="aac", bitrate=random.choice(["32k", "64k"]))

    def __call__(self, waveform):
        if random.random() < 0.2: waveform = self.add_noise(waveform)
        if random.random() < 0.2: waveform = self.bandpass_filter(waveform)
        if random.random() < 0.2: waveform = self.resample_degradation(waveform)
        if random.random() < 0.2: waveform = self.gain_perturb(waveform)
        if random.random() < 0.2: waveform = self.apply_clipping(waveform)
        if self.heavy_codec and self.has_pydub and random.random() < 0.2:
            if random.random() < 0.5:
                waveform = self.apply_mp3(waveform)
            else:
                waveform = self.apply_aac(waveform)
        return waveform

def load_audio(path):
    errors = []
    
    # 1. Default torchaudio
    try:
        return torchaudio.load(path)
    except Exception as e:
        errors.append(f"default_backend: {str(e)}")
        
    # 2. ffmpeg backend
    try:
        return torchaudio.load(path, backend="ffmpeg")
    except Exception as e:
        errors.append(f"ffmpeg_backend: {str(e)}")
        
    # 3. subprocess ffmpeg pipe to in-memory wav
    try:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(path),
            "-ac", "1", "-ar", "16000",
            "-f", "wav", "-"
        ]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg subprocess failed: {err.decode('utf-8', errors='ignore')}")
        return torchaudio.load(io.BytesIO(out), format="wav")
    except Exception as e:
        errors.append(f"subprocess: {str(e)}")
        
    raise RuntimeError(" | ".join(errors))

class ASVSpoofDataset(Dataset):
    def __init__(self, manifest_df, target_sr=16000, target_len=64000, mode="train", heavy_codec=True):
        self.df = manifest_df
        self.target_sr = target_sr
        self.target_len = target_len
        self.mode = mode
        self.aug = AudioAugmentation(target_sr, heavy_codec) if mode == "train" else None

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        audio_path = row['path']
        label = row['label'] 
        
        try:
            waveform, sr = load_audio(audio_path)
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            if sr != self.target_sr:
                waveform = torchaudio.functional.resample(waveform, sr, self.target_sr)
            if self.aug is not None:
                waveform = self.aug(waveform)
            waveform = pad_or_crop(waveform, self.target_len, self.mode)
            return waveform.squeeze(0), torch.tensor(label, dtype=torch.long), str(audio_path)
        except Exception as e:
            return None, f"{audio_path} | ERROR CHAIN: {str(e)}"

def build_manifest(data_dir, keys_dir, max_samples=None):
    logging.info("Building manifest...")
    flac_files = list(Path(data_dir).rglob("*.flac"))
    if not flac_files: raise ValueError(f"No FLAC files found in {data_dir}")
    logging.info(f"Found {len(flac_files)} FLAC files.")
    
    keys_file = None
    if keys_dir and Path(keys_dir).exists():
        txt_files = list(Path(keys_dir).rglob("*.txt"))
        
        # Priority 1: trial_metadata.txt
        for f in txt_files:
            if f.name == "trial_metadata.txt":
                keys_file = f
                break
                
        # Priority 2: ASVspoof2021.DF.cm.eval.trl.txt
        if not keys_file:
            for f in txt_files:
                if f.name == "ASVspoof2021.DF.cm.eval.trl.txt":
                    keys_file = f
                    break
                    
        # Priority 3: *.trl.txt
        if not keys_file:
            for f in txt_files:
                if f.name.endswith(".trl.txt"):
                    keys_file = f
                    break
                    
        if keys_file is None:
            logging.warning(
                f"No valid metadata file found in {keys_dir}. "
                "Expected trial_metadata.txt, ASVspoof2021.DF.cm.eval.trl.txt, or *.trl.txt"
            )
            
    labels_dict = {}
    speaker_dict = {}
    if keys_file:
        logging.info(f"Using exact keys file: {keys_file.absolute()}")
        parsed_count = 0
        bonafide_count = 0
        spoof_count = 0
        first_5 = []
        with open(keys_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    label_str = None
                    for p in parts:
                        if p.lower() in ['bonafide', 'spoof']:
                            label_str = p.lower()
                            break
                    if label_str:
                        spk = parts[0]
                        fn = parts[1]
                        lbl_val = 0 if label_str == 'bonafide' else 1
                        labels_dict[fn] = lbl_val
                        speaker_dict[fn] = spk
                        
                        parsed_count += 1
                        if lbl_val == 0: bonafide_count += 1
                        else: spoof_count += 1
                        
                        if len(first_5) < 5:
                            first_5.append(f"{fn}: {label_str} ({lbl_val})")
                            
        logging.info(f"Metadata parsed: {parsed_count} entries. Bonafide: {bonafide_count}, Spoof: {spoof_count}")
        if first_5:
            logging.info("First 5 parsed entries:")
            for entry in first_5:
                logging.info(f"  {entry}")
    else:
        logging.warning("No keys_dir provided. Defaulting to dummy labels.")
    
    data = []
    for p in flac_files:
        fn = p.stem
        if keys_file and fn not in labels_dict: continue
        label = labels_dict.get(fn, 1) 
        spk = speaker_dict.get(fn, "unknown")
        data.append({"path": str(p), "label": label, "speaker": spk, "filename": fn})
        
    df = pd.DataFrame(data)
    
    if len(df) > 0:
        logging.info("First 5 manifest entries and existence check:")
        for idx, row in df.head(5).iterrows():
            p = row['path']
            exists = Path(p).exists()
            logging.info(f"  {p} - Exists: {exists}")
            
    if max_samples and max_samples < len(df):
        half = max_samples // 2
        bonafides = df[df['label'] == 0]
        spoofs = df[df['label'] == 1]
        sample_bonafide = min(len(bonafides), half)
        sample_spoof = min(len(spoofs), max_samples - sample_bonafide)
        if sample_bonafide + sample_spoof < max_samples:
            sample_bonafide = min(len(bonafides), max_samples - sample_spoof)
        b_sample = bonafides.sample(n=sample_bonafide, random_state=42) if sample_bonafide > 0 else pd.DataFrame()
        s_sample = spoofs.sample(n=sample_spoof, random_state=42) if sample_spoof > 0 else pd.DataFrame()
        df = pd.concat([b_sample, s_sample]).sample(frac=1.0, random_state=42).reset_index(drop=True)
    return df

def create_splits(df):
    if df['speaker'].nunique() > 1 and "unknown" not in df['speaker'].values:
        logging.info("Speaker metadata found. Using GroupShuffleSplit.")
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, val_idx = next(gss.split(df, groups=df['speaker']))
        return df.iloc[train_idx].reset_index(drop=True), df.iloc[val_idx].reset_index(drop=True)
    else:
        logging.warning("No speaker metadata. Using StratifiedShuffleSplit.")
        sss = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, val_idx = next(sss.split(df, df['label']))
        return df.iloc[train_idx].reset_index(drop=True), df.iloc[val_idx].reset_index(drop=True)

class AudioCollate:
    def __init__(self, bad_audio_log):
        self.bad_audio_log = bad_audio_log
        
    def __call__(self, batch):
        valid_batch = []
        bad_files = []
        for b in batch:
            if b[0] is None: bad_files.append(b[1])
            else: valid_batch.append(b)
        if bad_files:
            with open(self.bad_audio_log, "a") as f:
                for bf in bad_files: f.write(bf + "\n")
        if not valid_batch:
            return torch.empty(0), torch.empty(0), []
        waves, labels, paths = zip(*valid_batch)
        return torch.stack(waves), torch.stack(labels), list(paths)

# ==============================================================================
# MAIN TRAINING LOOP
# ==============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--keys_dir", type=str, default="")
    parser.add_argument("--max_samples", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--audio_len", type=int, default=64000)
    parser.add_argument("--out_dir", type=str, default="aasist_official_output")
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--heavy_codec", action="store_true", help="Enable MP3/AAC aug")
    parser.add_argument("--resume_checkpoint", type=str, default="")
    args = parser.parse_args()

    if os.name == 'nt' and args.num_workers > 0:
        logging.warning("Running on Windows with num_workers > 0. Multiprocessing and pickling can be sensitive. If DataLoader crashes, try running with --num_workers 0.")

    os.makedirs(args.out_dir, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(os.path.join(args.out_dir, "train.log"))])

    bad_audio_log = os.path.join(args.out_dir, "bad_audio.txt")

    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    df = build_manifest(args.data_dir, args.keys_dir, args.max_samples)
    if len(df) == 0: return
    df.to_csv(os.path.join(args.out_dir, "manifest.csv"), index=False)
        
    train_df, val_df = create_splits(df)
    train_csv = os.path.join(args.out_dir, "train_split.csv")
    val_csv = os.path.join(args.out_dir, "val_split.csv")
    train_df.to_csv(train_csv, index=False)
    val_df.to_csv(val_csv, index=False)

    logging.info(f"Total manifest samples: {len(df)}")
    logging.info(f"Train samples: {len(train_df)}")
    logging.info(f"Val samples: {len(val_df)}")
    
    train_counts = train_df['label'].value_counts()
    val_counts = val_df['label'].value_counts()
    
    logging.info(f"Train counts -> Bonafide (0): {train_counts.get(0, 0)}, Spoof (1): {train_counts.get(1, 0)}")
    logging.info(f"Val counts -> Bonafide (0): {val_counts.get(0, 0)}, Spoof (1): {val_counts.get(1, 0)}")

    class_counts = train_counts
    if len(class_counts) < 2:
        raise ValueError(f"Dataset contains only {len(class_counts)} class(es). Both bonafide (0) and spoof (1) are required for training. Check keys/metadata parsing.")
        
    total = len(train_df)
    w0 = total / (2.0 * class_counts.get(0, 1))
    w1 = total / (2.0 * class_counts.get(1, 1))
    class_weights = torch.tensor([w0, w1], dtype=torch.float)

    train_dataset = ASVSpoofDataset(
        train_df,
        target_sr=16000,
        target_len=args.audio_len,
        mode="train",
        heavy_codec=args.heavy_codec,
    )

    val_dataset = ASVSpoofDataset(
        val_df,
        target_sr=16000,
        target_len=args.audio_len,
        mode="val",
        heavy_codec=False,
    )

    collate = AudioCollate(bad_audio_log)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers, collate_fn=collate)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers, collate_fn=collate)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AASIST(input_len=args.audio_len).to(device)
    ema = EMA(model, decay=0.999)
    
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    
    start_epoch = 1
    best_eer = float("inf")

    if args.resume_checkpoint and os.path.exists(args.resume_checkpoint):
        logging.info(f"Resuming from {args.resume_checkpoint}")
        ckpt = torch.load(args.resume_checkpoint, map_location=device)
        model.load_state_dict(ckpt["normal_model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        scheduler.load_state_dict(ckpt["scheduler_state_dict"])
        ema.load_state(ckpt["ema_state"])
        random.setstate(ckpt["rng_state_random"])
        np.random.set_state(ckpt["rng_state_np"])
        torch.set_rng_state(ckpt["rng_state_torch"])
        if ckpt.get("rng_state_cuda") is not None and torch.cuda.is_available():
            torch.cuda.set_rng_state_all(ckpt["rng_state_cuda"])
        start_epoch = ckpt["epoch"] + 1
        best_eer = ckpt["best_val_eer"]

    val_scores_file = os.path.join(args.out_dir, "val_scores.csv")
    val_details_file = os.path.join(args.out_dir, "val_details.csv")
    
    if start_epoch == 1:
        with open(val_scores_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Epoch", "Train_Loss", "Val_Loss", "Val_Acc", "Val_EER", "Val_AUC", "Precision", "Recall", "F1"])
        with open(val_details_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["epoch", "path", "label", "score", "prediction"])

    scaler = torch.amp.GradScaler("cuda", enabled=torch.cuda.is_available())

    logging.info("Starting training...")
    for epoch in range(start_epoch, args.epochs + 1):
        model.train()
        train_loss = 0
        valid_train_batches = 0
        optimizer_stepped = False
        for waves, labels, _ in train_loader:
            if len(waves) == 0: continue
            valid_train_batches += 1
            waves, labels = waves.to(device), labels.to(device)
            optimizer.zero_grad()
            
            with torch.amp.autocast("cuda", enabled=torch.cuda.is_available()):
                logits = model(waves)
                loss = criterion(logits, labels)
                
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            optimizer_stepped = True
            
            ema.update(model)
            train_loss += loss.item() * waves.size(0)
            
        if valid_train_batches == 0:
            raise RuntimeError("No valid training batches. Check audio paths/torchaudio loading.")
            
        train_loss /= max(len(train_dataset), 1)
        
        model.eval()
        ema.apply_shadow(model)
        
        val_loss, correct = 0, 0
        valid_val_batches = 0
        all_labels, all_scores, all_paths, all_preds = [], [], [], []
        
        with torch.no_grad():
            for waves, labels, paths in val_loader:
                if len(waves) == 0: continue
                valid_val_batches += 1
                waves, labels = waves.to(device), labels.to(device)
                with torch.amp.autocast("cuda", enabled=torch.cuda.is_available()):
                    logits = model(waves)
                    loss = criterion(logits, labels)
                val_loss += loss.item() * waves.size(0)
                
                probs = torch.softmax(logits, dim=1)[:, 1]
                preds = torch.argmax(logits, dim=1)
                
                correct += (preds == labels).sum().item()
                all_labels.extend(labels.cpu().numpy())
                all_scores.extend(probs.cpu().numpy())
                all_preds.extend(preds.cpu().numpy())
                all_paths.extend(paths)
                
        if valid_val_batches == 0:
            raise RuntimeError("No valid validation batches. Check audio paths/torchaudio loading.")
            
        val_loss /= max(len(val_dataset), 1)
        val_acc = correct / max(len(val_dataset), 1)
        
        if len(set(all_labels)) > 1:
            fpr, tpr, _ = roc_curve(all_labels, all_scores, pos_label=1)
            fnr = 1 - tpr
            eer = (fpr[np.nanargmin(np.absolute(fnr - fpr))] + fnr[np.nanargmin(np.absolute(fnr - fpr))]) / 2.0
            auc = roc_auc_score(all_labels, all_scores)
            prec = precision_score(all_labels, all_preds, zero_division=0)
            rec = recall_score(all_labels, all_preds, zero_division=0)
            f1 = f1_score(all_labels, all_preds, zero_division=0)
        else:
            eer, auc, prec, rec, f1 = 1.0, 0.0, 0.0, 0.0, 0.0
            
        with open(val_details_file, "a", newline="") as f:
            writer = csv.writer(f)
            for p, l, s, pred in zip(all_paths, all_labels, all_scores, all_preds):
                writer.writerow([epoch, p, l, s, pred])
            
        is_best = eer < best_eer
        if is_best: best_eer = eer
        
        ema_state_dict = {k: v.cpu().clone() for k, v in model.state_dict().items()}
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
            "val_accuracy": val_acc,
            "val_auc": auc
        }
        
        if is_best:
            torch.save(ckpt, os.path.join(args.out_dir, "best_model.pth"))
            logging.info(f"--> Saved best model (EER: {best_eer:.4f})")
            
        torch.save(ckpt, os.path.join(args.out_dir, "last_model.pth"))
        
        if optimizer_stepped:
            scheduler.step()
        logging.info(f"Ep {epoch:03d} | TL: {train_loss:.4f} | VL: {val_loss:.4f} | Acc: {val_acc:.4f} | EER: {eer:.4f} | AUC: {auc:.4f}")
        
        with open(val_scores_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([epoch, train_loss, val_loss, val_acc, eer, auc, prec, rec, f1])

if __name__ == "__main__":
    main()
