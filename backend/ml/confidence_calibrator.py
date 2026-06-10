import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

class TemperatureScaler(nn.Module):
    def __init__(self):
        super().__init__()
        self.temperature = nn.Parameter(torch.ones(1) * 1.5)

    def forward(self, logits):
        return self.temperature_scale(logits)

    def temperature_scale(self, logits):
        """
        Perform temperature scaling on logits
        """
        temperature = self.temperature.unsqueeze(1).expand(logits.size(0), logits.size(1))
        return logits / temperature
        
    def fit(self, logits, labels, lr=0.01, max_iter=500):
        nll_criterion = nn.CrossEntropyLoss()
        optimizer = optim.LBFGS([self.temperature], lr=lr, max_iter=max_iter)
        
        logits_tensor = torch.tensor(logits, dtype=torch.float32)
        labels_tensor = torch.tensor(labels, dtype=torch.long)
        
        def eval():
            optimizer.zero_grad()
            loss = nll_criterion(self.temperature_scale(logits_tensor), labels_tensor)
            loss.backward()
            return loss
            
        optimizer.step(eval)
        print(f"Optimal temperature: {self.temperature.item():.3f}")

    def transform(self, logits):
        logits_tensor = torch.tensor(logits, dtype=torch.float32)
        with torch.no_grad():
            scaled_logits = self.temperature_scale(logits_tensor)
            probs = torch.nn.functional.softmax(scaled_logits, dim=1)
        return probs.numpy()

    def save(self, path):
        with open(path, 'w') as f:
            json.dump({"temperature": self.temperature.item()}, f)

    def load(self, path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                self.temperature.data = torch.tensor([data["temperature"]], dtype=torch.float32)

# Global instance for runtime use
_calibrator = None

def get_calibrator():
    global _calibrator
    if _calibrator is None:
        _calibrator = TemperatureScaler()
        from pathlib import Path
        calib_path = Path(__file__).resolve().parents[1] / "config" / "audio_temperature.json"
        if os.path.exists(calib_path):
            _calibrator.load(calib_path)
    return _calibrator
