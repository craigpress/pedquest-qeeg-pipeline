"""Stub for spectrogram CSV ingestion (future work).

Spectrogram CSVs from Research-Spectrograms panel contain multi-value
FFT_Spectrogram and Rhythmicity Spectrogram columns. These require a
different parsing strategy (column-per-frequency-bin or pivot) and are
not yet processed by the pipeline. Files are classified and stored for
future use.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def log_spectrogram_files(files: list[Path]) -> None:
    """Log spectrogram CSV paths for a patient (no parsing yet)."""
    for f in files:
        logger.info("Spectrogram CSV detected (not processed): %s", f)
