"""
fft_model.py - Lightweight FFT classifier architectures.

Supported:
  - "resnet18"       : ResNet-18 with first conv adapted for 1-channel input (default).
  - "efficientnet_b0": EfficientNet-B0 with first conv adapted for 1-channel input.

Both output a single binary logit (real=0, fake=1).
Loss: BCEWithLogitsLoss (default) or Focal Loss.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# FFT ResNet-18 (default)
# ---------------------------------------------------------------------------

class FFTResNet18(nn.Module):
    """
    ResNet-18 adapted for 1-channel FFT spectrum input.
    Outputs a single logit for binary classification.
    """

    def __init__(self) -> None:
        super().__init__()
        from torchvision.models import resnet18, ResNet18_Weights
        backbone = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)

        # Replace first conv: 3-channel -> 1-channel, same kernel & stride
        original_conv = backbone.conv1
        backbone.conv1 = nn.Conv2d(
            in_channels=1,
            out_channels=original_conv.out_channels,
            kernel_size=original_conv.kernel_size,
            stride=original_conv.stride,
            padding=original_conv.padding,
            bias=False,
        )
        # Initialise new conv by averaging the pretrained RGB weights across channels
        with torch.no_grad():
            backbone.conv1.weight.copy_(
                original_conv.weight.mean(dim=1, keepdim=True)
            )

        # Replace final FC for binary output
        in_features = backbone.fc.in_features
        backbone.fc = nn.Linear(in_features, 1)

        self.backbone = backbone

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)


# ---------------------------------------------------------------------------
# FFT EfficientNet-B0 (optional)
# ---------------------------------------------------------------------------

class FFTEfficientNetB0(nn.Module):
    """
    EfficientNet-B0 adapted for 1-channel FFT spectrum input.
    Outputs a single logit for binary classification.
    """

    def __init__(self) -> None:
        super().__init__()
        from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights
        backbone = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)

        # Patch the first convolutional layer
        first_conv = backbone.features[0][0]
        new_conv = nn.Conv2d(
            in_channels=1,
            out_channels=first_conv.out_channels,
            kernel_size=first_conv.kernel_size,
            stride=first_conv.stride,
            padding=first_conv.padding,
            bias=False,
        )
        with torch.no_grad():
            new_conv.weight.copy_(first_conv.weight.mean(dim=1, keepdim=True))
        backbone.features[0][0] = new_conv

        # Replace classifier for binary output
        in_features = backbone.classifier[1].in_features
        backbone.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(in_features, 1),
        )

        self.backbone = backbone

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)


# ---------------------------------------------------------------------------
# Focal Loss (optional alternative to BCEWithLogitsLoss)
# ---------------------------------------------------------------------------

class FocalLossBinary(nn.Module):
    """
    Binary focal loss on logits with optional alpha weighting.
    BCEWithLogitsLoss is equivalent when gamma=0.
    """

    def __init__(self, gamma: float = 2.0, alpha: float = 0.75) -> None:
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        logit = logits.view(-1).float()
        t = targets.view(-1).float()

        log_p = F.logsigmoid(logit)
        log_1_p = F.logsigmoid(-logit)
        bce = -(t * log_p + (1.0 - t) * log_1_p)

        p = torch.sigmoid(logit)
        p_t = p * t + (1.0 - p) * (1.0 - t)
        focal = torch.pow((1.0 - p_t).clamp(min=1e-6), self.gamma) * bce

        alpha_t = self.alpha * t + (1.0 - self.alpha) * (1.0 - t)
        return (alpha_t * focal).mean()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_model(arch: str) -> nn.Module:
    """Return the requested FFT model."""
    if arch == "resnet18":
        return FFTResNet18()
    elif arch == "efficientnet_b0":
        return FFTEfficientNetB0()
    else:
        raise ValueError(f"Unknown arch '{arch}'. Choose 'resnet18' or 'efficientnet_b0'.")


def build_loss(loss_fn: str, gamma: float = 2.0, alpha: float = 0.75) -> nn.Module:
    """Return the requested loss function."""
    if loss_fn == "bce":
        return nn.BCEWithLogitsLoss()
    elif loss_fn == "focal":
        return FocalLossBinary(gamma=gamma, alpha=alpha)
    else:
        raise ValueError(f"Unknown loss_fn '{loss_fn}'. Choose 'bce' or 'focal'.")
