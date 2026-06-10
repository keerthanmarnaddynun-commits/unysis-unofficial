import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

class GradCAM:
    def __init__(self, model: nn.Module, target_layer: nn.Module):
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None
        
        self.target_layer.register_forward_hook(self.save_activation)
        self.target_layer.register_full_backward_hook(self.save_gradient)
        
    def save_activation(self, module, input, output):
        self.activations = output

    def save_gradient(self, module, grad_input, grad_output):
        # register_full_backward_hook returns grad_output as a tuple
        self.gradients = grad_output[0]
        
    def generate(self, input_tensor: torch.Tensor):
        # Enable gradients for input to ensure graph traces through hooks
        input_tensor.requires_grad_(True)
        
        # Forward pass
        self.model.zero_grad()
        output = self.model(input_tensor)
        
        # Backward pass
        output.backward()
        
        if self.gradients is None or self.activations is None:
            raise RuntimeError("Gradients or activations were not captured. Check layer hook.")
            
        # Get gradients and activations
        gradients = self.gradients.cpu().data.numpy()[0]
        activations = self.activations.cpu().data.numpy()[0]
        
        # Weight activations by pooled gradients
        weights = np.mean(gradients, axis=(1, 2))
        cam = np.zeros(activations.shape[1:], dtype=np.float32)
        
        for i, w in enumerate(weights):
            cam += w * activations[i]
            
        cam = np.maximum(cam, 0) # ReLU
        
        # Normalize
        cam_max = np.max(cam)
        if cam_max != 0:
            cam = cam / cam_max
            
        return cam

def overlay_heatmap(original_img_np: np.ndarray, cam: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    """
    Overlays the CAM heatmap onto the original RGB image.
    original_img_np: uint8 RGB numpy array (e.g. aligned face crop).
    cam: 2D float numpy array [0, 1].
    """
    h, w, _ = original_img_np.shape
    heatmap = cv2.resize(cam, (w, h))
    heatmap = np.uint8(255 * heatmap)
    heatmap = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    
    superimposed_img = heatmap * alpha + original_img_np * (1.0 - alpha)
    return np.uint8(np.clip(superimposed_img, 0, 255))
