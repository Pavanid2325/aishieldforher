"""Locate trusted model assets in a checkout or mounted container bundle."""
import os
from pathlib import Path


def model_root():
    configured = os.getenv('MODEL_ROOT')
    return Path(configured) if configured else Path(__file__).resolve().parents[1] / 'assets' / 'models'
