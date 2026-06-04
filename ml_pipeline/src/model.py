import torch.nn as nn
from efficientnet_pytorch import EfficientNet
import config

class DeepfakeClassifier(nn.Module):
    def __init__(self, pretrained=True):
        super(DeepfakeClassifier, self).__init__()
        
        if pretrained:
            self.model = EfficientNet.from_pretrained('efficientnet-b0')
        else:
            self.model = EfficientNet.from_name('efficientnet-b0')
            
        # Modify the final layer for binary classification
        num_ftrs = self.model._fc.in_features
        dropout_p = getattr(config, "HEAD_DROPOUT", 0.3)
        self.model._fc = nn.Sequential(
            nn.Dropout(p=dropout_p),
            nn.Linear(num_ftrs, 2),
        )
        
    def forward(self, x):
        return self.model(x)
