import torch.nn as nn
from efficientnet_pytorch import EfficientNet

class DeepfakeClassifier(nn.Module):
    def __init__(self, pretrained=True):
        super(DeepfakeClassifier, self).__init__()
        
        if pretrained:
            self.model = EfficientNet.from_pretrained('efficientnet-b0')
        else:
            self.model = EfficientNet.from_name('efficientnet-b0')
            
        # Modify the final layer for binary classification
        num_ftrs = self.model._fc.in_features
        self.model._fc = nn.Linear(num_ftrs, 2)
        
    def forward(self, x):
        return self.model(x)
