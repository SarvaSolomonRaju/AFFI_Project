"""
model.py — Neural network architectures for Task 2
====================================================
Contains the LSTM classifier used in the hurdle model.
Separated from training script so evaluation and inference
can import it without importing training logic.

Junior-dev lesson:
  Model definitions go in their own file. Training logic,
  evaluation logic, and inference logic are SEPARATE files
  that all import from here. This is the "single source of truth"
  for architecture — if you change hidden_dim here, it changes
  everywhere.
"""

import torch
import torch.nn as nn


class LSTMClassifier(nn.Module):
    """
    Binary LSTM classifier for runoff event detection.

    Architecture:
      Input (seq_len, n_features)
        → LSTM (hidden_dim, num_layers, dropout)
        → Last hidden state
        → Linear(hidden_dim, 1)
        → Sigmoid (applied externally via BCEWithLogitsLoss)

    The model outputs RAW LOGITS (not probabilities).
    Apply sigmoid yourself during inference.
    This is standard practice because BCEWithLogitsLoss is
    numerically more stable than BCE + manual sigmoid.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(hidden_dim, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Parameters
        ----------
        x : Tensor of shape (batch, seq_len, input_dim)

        Returns
        -------
        logits : Tensor of shape (batch,)
        """
        _, (h_n, _) = self.lstm(x)       # h_n: (num_layers, batch, hidden)
        last_hidden = h_n[-1]             # (batch, hidden)
        logits = self.head(last_hidden)   # (batch, 1)
        return logits.squeeze(-1)         # (batch,)
