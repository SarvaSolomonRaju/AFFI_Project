from __future__ import annotations
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from hydraulics.resunet import ResBlock, EncoderBlock, DecoderBlock, ResUNet


class TestResBlock:
    def test_same_channels(self):
        block = ResBlock(32, 32)
        x = torch.randn(2, 32, 64, 64)
        out = block(x)
        assert out.shape == (2, 32, 64, 64)

    def test_different_channels(self):
        block = ResBlock(32, 64)
        x = torch.randn(2, 32, 64, 64)
        out = block(x)
        assert out.shape == (2, 64, 64, 64)


class TestEncoderBlock:
    def test_with_downsample(self):
        enc = EncoderBlock(32, 64, downsample=True)
        x = torch.randn(2, 32, 64, 64)
        down, skip = enc(x)
        assert skip.shape == (2, 64, 64, 64)
        assert down.shape == (2, 64, 32, 32)

    def test_without_downsample(self):
        enc = EncoderBlock(4, 32, downsample=False)
        x = torch.randn(2, 4, 256, 256)
        down, skip = enc(x)
        assert skip.shape == (2, 32, 256, 256)
        assert down.shape == skip.shape


class TestDecoderBlock:
    def test_upsample_and_concat(self):
        dec = DecoderBlock(128, 64, 64)
        x = torch.randn(2, 128, 32, 32)
        skip = torch.randn(2, 64, 64, 64)
        out = dec(x, skip)
        assert out.shape == (2, 64, 64, 64)


class TestResUNet:
    def test_instantiation(self):
        model = ResUNet(in_channels=4, out_channels=1)
        assert model is not None

    def test_forward_shape(self):
        model = ResUNet(in_channels=4, out_channels=1)
        x = torch.randn(2, 4, 256, 256)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (2, 1, 256, 256)

    def test_output_nonnegative(self):
        model = ResUNet(in_channels=4, out_channels=1)
        x = torch.randn(2, 4, 64, 64)
        with torch.no_grad():
            out = model(x)
        assert (out >= 0).all(), "ReLU head should produce non-negative outputs"

    def test_parameter_count(self):
        model = ResUNet(in_channels=4, out_channels=1)
        n_params = model.count_parameters()
        assert 1_000_000 < n_params < 15_000_000, f"Expected ~10M params, got {n_params:,}"

    def test_smaller_input(self):
        model = ResUNet(in_channels=4, out_channels=1)
        x = torch.randn(1, 4, 64, 64)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (1, 1, 64, 64)
