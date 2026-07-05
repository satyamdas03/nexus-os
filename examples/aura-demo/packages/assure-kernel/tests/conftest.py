"""Shared fixtures for assure-kernel tests."""

import sys
from pathlib import Path

import pytest

# Make the original aura-demo rules_engine importable for parity testing.
AURA_BACKEND = Path(__file__).parent.parent.parent / "backend"
if str(AURA_BACKEND) not in sys.path:
    sys.path.insert(0, str(AURA_BACKEND))
