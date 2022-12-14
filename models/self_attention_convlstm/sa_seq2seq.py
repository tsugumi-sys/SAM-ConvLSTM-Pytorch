from typing import Tuple, Union, Optional
import sys

import torch
from torch import nn
from torch.utils.data import Dataset
from torch.nn.modules.loss import _Loss
from torch.nn import functional as F

sys.path.append(".")
from models.self_attention_convlstm.sa_convlstm import SAConvLSTM
from common.constans import WeightsInitializer


class SASeq2Seq(nn.Module):
    def __init__(
        self,
        attention_hidden_dims: int,
        num_channels: int,
        kernel_size: Union[int, Tuple],
        num_kernels: int,
        padding: Union[int, Tuple, str],
        activation: str,
        frame_size: Tuple,
        num_layers: int,
        input_seq_length: int,
        out_channels: Optional[int] = None,
        weights_initializer: Optional[str] = WeightsInitializer.Zeros.value,
        return_sequences: bool = False,
    ) -> None:
        """Initialize SeqtoSeq

        Args:
            num_channels (int): [Number of input channels]
            kernel_size (int): [kernel size]
            num_kernels (int): [Number of kernels]
            padding (Union[str, Tuple]): ['same', 'valid' or (int, int)]
            activation (str): [the name of activation function]
            frame_size (Tuple): [height and width]
            num_layers (int): [the number of layers]
        """
        super(SASeq2Seq, self).__init__()
        self.attention_hidden_dims = attention_hidden_dims
        self.num_channels = num_channels
        self.kernel_size = kernel_size
        self.num_kernels = num_kernels
        self.padding = padding
        self.activation = activation
        self.frame_size = frame_size
        self.num_layers = num_layers
        self.input_seq_length = input_seq_length
        self.out_channels = out_channels if out_channels is not None else num_channels
        self.weights_initializer = weights_initializer
        self.return_sequences = return_sequences

        self.sequential = nn.Sequential()

        # Add first layer (Different in_channels than the rest)
        self.sequential.add_module(
            "sa_convlstm1",
            SAConvLSTM(
                attention_hidden_dims=self.attention_hidden_dims,
                in_channels=self.num_channels,
                out_channels=self.num_kernels,
                kernel_size=self.kernel_size,
                padding=self.padding,
                activation=self.activation,
                frame_size=self.frame_size,
                weights_initializer=self.weights_initializer,
            ),
        )

        self.sequential.add_module(
            "layernorm1",
            nn.LayerNorm([self.num_kernels, self.input_seq_length, *self.frame_size]),
        )

        # Add the rest of the layers
        for layer_idx in range(2, self.num_layers + 1):
            self.sequential.add_module(
                f"sa_convlstm{layer_idx}",
                SAConvLSTM(
                    attention_hidden_dims=self.attention_hidden_dims,
                    in_channels=self.num_kernels,
                    out_channels=self.num_kernels,
                    kernel_size=self.kernel_size,
                    padding=self.padding,
                    activation=self.activation,
                    frame_size=self.frame_size,
                    weights_initializer=self.weights_initializer,
                ),
            )

            self.sequential.add_module(
                f"layernorm{layer_idx}",
                nn.LayerNorm(
                    [self.num_kernels, self.input_seq_length, *self.frame_size]
                ),
            )

        self.sequential.add_module(
            f"conv3d",
            nn.Conv3d(
                in_channels=self.num_kernels,
                out_channels=self.out_channels,
                kernel_size=(3, 3, 3),
                padding="same",
            ),
        )

        self.sequential.add_module("sigmoid", nn.Sigmoid())

    def forward(self, X: torch.Tensor):
        # Forward propagation through all the layers
        output = self.sequential(X)

        if self.return_sequences is True:
            return output

        return output[:, :, -1:, ...]


if __name__ == "__main__":
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    input_X = torch.rand((5, 3, 6, 16, 16), dtype=torch.float, device=DEVICE)
    model = (
        SASeq2Seq(
            attention_hidden_dims=4,
            num_channels=3,
            kernel_size=3,
            num_kernels=4,
            padding="same",
            activation="relu",
            frame_size=(16, 16),
            num_layers=1,
            input_seq_length=6,
            return_sequences=True,
        )
        .to(DEVICE)
        .to(torch.float)
    )
    y = model.forward(input_X)
    print(y.shape)
