import torch
import torch.nn as nn
import torch.nn.functional as F

def patch_mps_adaptive_pooling():
    # Patch nn.AdaptiveAvgPool2d
    orig_avg_forward = nn.AdaptiveAvgPool2d.forward
    def avg_forward_patch(self, input):
        if input.device.type == "mps":
            return orig_avg_forward(self, input.cpu()).to(input.device)
        return orig_avg_forward(self, input)
    nn.AdaptiveAvgPool2d.forward = avg_forward_patch

    # Patch F.adaptive_avg_pool2d
    orig_avg_func = F.adaptive_avg_pool2d
    def avg_func_patch(input, output_size):
        if torch.is_tensor(input) and input.device.type == "mps":
            return orig_avg_func(input.cpu(), output_size).to(input.device)
        return orig_avg_func(input, output_size)
    F.adaptive_avg_pool2d = avg_func_patch
    # Some torch versions bind this directly under torch
    if hasattr(torch, "adaptive_avg_pool2d"):
        torch.adaptive_avg_pool2d = avg_func_patch

    # Patch nn.AdaptiveMaxPool2d
    orig_max_forward = nn.AdaptiveMaxPool2d.forward
    def max_forward_patch(self, input):
        if input.device.type == "mps":
            return orig_max_forward(self, input.cpu()).to(input.device)
        return orig_max_forward(self, input)
    nn.AdaptiveMaxPool2d.forward = max_forward_patch

    # Patch F.adaptive_max_pool2d
    orig_max_func = F.adaptive_max_pool2d
    def max_func_patch(input, output_size, return_indices=False):
        if torch.is_tensor(input) and input.device.type == "mps":
            if return_indices:
                out, idx = orig_max_func(input.cpu(), output_size, return_indices=True)
                return out.to(input.device), idx.to(input.device)
            return orig_max_func(input.cpu(), output_size).to(input.device)
        return orig_max_func(input, output_size, return_indices)
    F.adaptive_max_pool2d = max_func_patch

# Apply the patch immediately upon import
patch_mps_adaptive_pooling()
print("[mps_patch] Applied Adaptive Pooling fallback to CPU for MPS device.")
