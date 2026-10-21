"""Optional local-only Chronos-2 zero-shot adapter (no weights bundled).

The public tensor API is documented in amazon-science/chronos-forecasting:
src/chronos/chronos2/pipeline.py, predict_quantiles. This optional integration
has no import-time dependency and is not a validated market model. It sees raw
past source-close prices only, with real NaNs preserved, and no future cohort.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import math
from pathlib import Path
import re

VERSION = "seven-chronos2-optional-1.0"
VALIDATION_STATUS = "adapter_only_no_real_weights_validation"
_ALLOWED_SUFFIXES = {".json", ".safetensors", ".md", ".txt"}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_local_model(model_path, expected_hashes):
    """Verify every local model file against an independently trusted manifest.

    No pickle weights/custom Python are accepted. Do not manufacture this
    manifest from an untrusted directory and treat that as publisher evidence.
    Credentials must never be put in a model directory or hash manifest.
    """
    if not isinstance(expected_hashes, dict) or not expected_hashes:
        raise ValueError("A trusted mapping of model-relative filenames to SHA-256 hashes is required")
    root = Path(model_path).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Chronos-2 model_path must be an existing local directory")
    actual = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlinks are not accepted inside the local model directory")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() not in _ALLOWED_SUFFIXES or "adapter" in path.name.lower():
            raise ValueError(f"Unsupported local model file: {relative}; use base Chronos-2 safetensors only")
        # Tokens/session files are not part of a local model and are never read.
        if any(word in path.name.lower() for word in ("token", "credential", "cookie", "secret")):
            raise ValueError("Remove credential-like files from the model directory; their contents were not read")
        if relative not in expected_hashes:
            raise ValueError(f"File absent from trusted manifest: {relative}")
        expected = expected_hashes[relative]
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            raise ValueError(f"Invalid SHA-256 for {relative}")
        actual[relative] = _sha256(path)
        if actual[relative] != expected.lower():
            raise ValueError(f"Local model checksum mismatch: {relative}")
    if set(actual) != set(expected_hashes):
        raise ValueError("Trusted manifest references missing or unsafe model files")
    if "config.json" not in actual or not any(key.endswith(".safetensors") for key in actual):
        raise ValueError("A config.json and safetensors weights are required")
    return root, actual


@dataclass
class LocalChronos2:
    pipeline: object
    metadata: dict
    context_length: int = 672
    prediction_length: int = 168

    def predict(self, source_close, reference, batch_size=8):
        """Return last-horizon median prices and returns; no refitting.

        source_close is [N,672], raw close price, where missing hours are NaN.
        Each sample is independent (cross_learning=False); no future values or
        other samples' later context are supplied as covariates.
        """
        import numpy as np
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        values = np.asarray(source_close, dtype=np.float32)
        refs = np.asarray(reference, dtype=np.float64).reshape(-1)
        if values.ndim != 2 or values.shape[1] != self.context_length or len(refs) != len(values):
            raise ValueError(f"Expected source_close[N,{self.context_length}] and matching reference[N]")
        if np.isinf(values).any() or ((~np.isnan(values)) & (values <= 0)).any():
            raise ValueError("Observed source-close values must be positive finite prices")
        if not np.isfinite(refs).all() or (refs <= 0).any():
            raise ValueError("Reference prices must be positive finite")
        if len(values) and np.isnan(values).all(axis=1).any():
            raise ValueError("An all-missing price history cannot be forecast")
        paths = []
        for start in range(0, len(values), batch_size):
            chunk = values[start:start + batch_size]
            # Chronos-2 [batch,variates,history] tensor/array API; NaNs stay NaN.
            quantiles, _ = self.pipeline.predict_quantiles(
                inputs=chunk[:, None, :], prediction_length=self.prediction_length,
                quantile_levels=[0.5], context_length=self.context_length,
                batch_size=batch_size, cross_learning=False,
            )
            if len(quantiles) != len(chunk):
                raise ValueError("Chronos-2 returned an unexpected sample count")
            for item in quantiles:
                if hasattr(item, "detach"):
                    item = item.detach().float().cpu().numpy()
                item = np.asarray(item, dtype=np.float64)
                if item.shape != (1, self.prediction_length, 1):
                    raise ValueError(f"Unexpected Chronos-2 quantile shape: {item.shape}")
                path = item[0, :, 0]
                if not np.isfinite(path).all() or (path <= 0).any():
                    raise ValueError("Chronos-2 produced nonpositive/nonfinite source prices")
                paths.append(path)
        median_paths = np.stack(paths) if paths else np.empty((0, self.prediction_length))
        final_price = median_paths[:, -1]
        return {"prediction_return_7d": final_price / refs - 1,
                "prediction_price_7d": final_price, "median_path": median_paths,
                "metadata": self.metadata.copy()}


def load_chronos2(model_path, expected_hashes, device="auto", *, allow_download=False,
                 context_length=672, prediction_length=168):
    """Load an explicitly supplied, hashed local base-model directory only.

    Downloads are deliberately not implemented in this research adapter. The
    user may separately obtain the official model and its trusted manifest.
    This loader never installs packages, downloads files or fine-tunes weights.
    """
    if allow_download:
        raise ValueError("This adapter is local-only; obtain model weights explicitly outside the runner, then provide model_path and trusted hashes")
    for label, number in (("context_length", context_length), ("prediction_length", prediction_length)):
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError(f"{label} must be a positive integer")
    root, hashes = verify_local_model(model_path, expected_hashes)
    try:
        from chronos import Chronos2Pipeline
    except ImportError as exc:
        raise ImportError("Chronos-2 is optional and not installed; install its official chronos-forecasting package in a compatible separate environment before enabling this adapter") from exc
    from .neural import resolve_device
    selected = resolve_device(device)
    pipeline = Chronos2Pipeline.from_pretrained(
        str(root), device_map=str(selected), local_files_only=True,
        trust_remote_code=False, use_safetensors=True,
    )
    try:
        package_version = importlib.metadata.version("chronos-forecasting")
    except importlib.metadata.PackageNotFoundError:
        package_version = "unknown"
    metadata = {"version": VERSION, "name": "chronos2_zero_shot",
                "validation_status": VALIDATION_STATUS, "model_path": str(root),
                "file_sha256": hashes, "package_version": package_version,
                "device_used": str(selected), "downloads_allowed": False,
                "context_length": context_length, "prediction_length": prediction_length,
                "statistic": "last_horizon_median", "cross_learning": False,
                "input": "past_raw_source_close_nan_preserved", "fine_tuned": False}
    return LocalChronos2(pipeline, metadata, context_length, prediction_length)
