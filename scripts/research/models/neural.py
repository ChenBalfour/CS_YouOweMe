"""Small, reloadable seven-day-return models; importing this module needs no torch.

The four adapters receive the same past-only sequence and tabular information.
Preprocessing is deliberately external: fit its statistics on train only, and
persist its schema alongside this model directory. No market access occurs here.
"""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random
import time

VERSION = "seven-neural-1.0"
MODEL_NAMES = ("dlinear", "lstm", "transformer", "gated_lstm_transformer")
_ARCH_DEFAULTS = {
    "sequence_length": 672, "sequence_dim": 6, "tabular_dim": 49,
    "hidden_dim": 32, "num_layers": 1, "nhead": 4, "dropout": 0.1,
    "short_length": 24, "moving_average_kernel": 25,
}
_TRAIN_DEFAULTS = {
    "batch_size": 8, "epochs": 50, "patience": 8, "learning_rate": 1e-3,
    "weight_decay": 1e-4, "seed": 20261021, "min_delta": 0.0,
    "gradient_clip": 1.0,
}


def _dependencies():
    try:
        import numpy as np
        import torch
    except ImportError as exc:
        raise ImportError("Neural models require numpy and a compatible PyTorch installation; install the optional training dependencies in the VS Code kernel.") from exc
    return np, torch


def _write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_device(device="auto"):
    """Return a real torch.device; explicit CUDA requests never fall back."""
    _, torch = _dependencies()
    requested = str(device)
    if requested == "auto":
        selected = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        reason = "CUDA available" if selected.type == "cuda" else "CUDA unavailable; auto selected CPU"
        print(f"[neural] {reason}: {selected}", flush=True)
    else:
        selected = torch.device(requested)
    if selected.type not in {"cpu", "cuda"}:
        raise ValueError("Only cpu, cuda[:index], or auto is supported")
    if selected.type == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is unavailable in this VS Code Python kernel; no CPU fallback was attempted")
        index = selected.index if selected.index is not None else torch.cuda.current_device()
        if index >= torch.cuda.device_count():
            raise ValueError(f"CUDA device index {index} does not exist")
        selected = torch.device(f"cuda:{index}")
    return selected


def _architecture(config=None):
    config = config or {}
    result = {key: config.get(key, value) for key, value in _ARCH_DEFAULTS.items()}
    for key in ("sequence_length", "sequence_dim", "tabular_dim", "hidden_dim", "num_layers", "nhead", "short_length", "moving_average_kernel"):
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{key} must be a positive integer")
    if result["hidden_dim"] % result["nhead"]:
        raise ValueError("hidden_dim must be divisible by nhead")
    if result["short_length"] >= result["sequence_length"]:
        raise ValueError("short_length must be shorter than sequence_length")
    if result["moving_average_kernel"] % 2 != 1:
        raise ValueError("moving_average_kernel must be odd")
    result["dropout"] = float(result["dropout"])
    if not 0 <= result["dropout"] < 1:
        raise ValueError("dropout must be in [0,1)")
    return result


def _training_config(config=None):
    config = dict(config or {})
    if "max_epochs" in config:
        if "epochs" in config and config["epochs"] != config["max_epochs"]:
            raise ValueError("epochs and max_epochs disagree")
        config["epochs"] = config["max_epochs"]
    allowed = set(_ARCH_DEFAULTS) | set(_TRAIN_DEFAULTS) | {"max_epochs"}
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"Unknown neural config keys: {sorted(unknown)}")
    result = {key: config.get(key, value) for key, value in _TRAIN_DEFAULTS.items()}
    for key in ("batch_size", "epochs", "patience", "seed"):
        value = result[key]
        minimum = 0 if key == "seed" else 1
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"Invalid integer {key}")
    for key in ("learning_rate", "weight_decay", "min_delta", "gradient_clip"):
        result[key] = float(result[key])
        if not math.isfinite(result[key]) or result[key] < 0:
            raise ValueError(f"Invalid finite nonnegative {key}")
    if result["learning_rate"] == 0 or result["gradient_clip"] == 0:
        raise ValueError("learning_rate and gradient_clip must be positive")
    return result


def build_network(name, config=None):
    """Create an untrained model with forward(sequence, tabular) -> [batch]."""
    if name not in MODEL_NAMES:
        raise ValueError(f"Unsupported neural model: {name}")
    _, torch = _dependencies()
    nn = torch.nn
    cfg = _architecture(config)
    length, channels, tabdim, hidden = (cfg[k] for k in ("sequence_length", "sequence_dim", "tabular_dim", "hidden_dim"))

    def encoder():
        layer = nn.TransformerEncoderLayer(
            d_model=hidden, nhead=cfg["nhead"], dim_feedforward=hidden * 2,
            dropout=cfg["dropout"], batch_first=True,
        )
        return nn.TransformerEncoder(layer, num_layers=cfg["num_layers"], enable_nested_tensor=False)

    def lstm():
        return nn.LSTM(channels, hidden, num_layers=cfg["num_layers"], batch_first=True,
                       dropout=cfg["dropout"] if cfg["num_layers"] > 1 else 0.0)

    def head(inputdim):
        return nn.Sequential(nn.Linear(inputdim, hidden), nn.GELU(), nn.Dropout(cfg["dropout"]), nn.Linear(hidden, 1))

    class DLinear(nn.Module):
        """Shared temporal trend/residual linears plus a linear static branch.

        This is a DLinear adaptation to a single +168h return, not a forecast of
        every future hour. All six channels, including masks, are provided.
        """
        def __init__(self):
            super().__init__()
            self.kernel = cfg["moving_average_kernel"]
            self.trend = nn.Linear(length, 1)
            self.seasonal = nn.Linear(length, 1)
            self.output = nn.Linear(channels + tabdim, 1)

        def forward(self, sequence, tabular):
            series = sequence.transpose(1, 2)
            padding = (self.kernel - 1) // 2
            padded = torch.nn.functional.pad(series, (padding, padding), mode="replicate")
            trend = torch.nn.functional.avg_pool1d(padded, self.kernel, stride=1)
            values = self.trend(trend) + self.seasonal(series - trend)
            return self.output(torch.cat((values.squeeze(-1), tabular), dim=-1)).squeeze(-1)

    class SmallLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = lstm()
            self.output = head(hidden + tabdim)

        def forward(self, sequence, tabular):
            _, (last, _) = self.encoder(sequence)
            return self.output(torch.cat((last[-1], tabular), dim=-1)).squeeze(-1)

    class SmallTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.projection = nn.Linear(channels, hidden)
            self.position = nn.Parameter(torch.randn(1, length, hidden) * 0.02)
            self.encoder = encoder()
            self.output = head(hidden + tabdim)

        def forward(self, sequence, tabular):
            encoded = self.encoder(self.projection(sequence) + self.position)
            return self.output(torch.cat((encoded[:, -1], tabular), dim=-1)).squeeze(-1)

    class GatedLSTMTransformer(nn.Module):
        """Local 24h LSTM queries the preceding 648h Transformer context.

        New task-specific weights; no thesis traffic checkpoint is reused.
        Both branches train together, since no matching stage-one checkpoint
        exists for this market task.
        """
        def __init__(self):
            super().__init__()
            self.short_length = cfg["short_length"]
            self.local = lstm()
            self.projection = nn.Linear(channels, hidden)
            self.position = nn.Parameter(torch.randn(1, length - self.short_length, hidden) * 0.02)
            self.long = encoder()
            self.cross = nn.MultiheadAttention(hidden, cfg["nhead"], dropout=cfg["dropout"], batch_first=True)
            self.cross_norm = nn.LayerNorm(hidden)
            self.ffn = nn.Sequential(nn.Linear(hidden, hidden * 2), nn.GELU(), nn.Dropout(cfg["dropout"]), nn.Linear(hidden * 2, hidden))
            self.ffn_norm = nn.LayerNorm(hidden)
            self.gate = nn.Linear(hidden, 1)
            self.output = head(hidden + tabdim)

        def forward(self, sequence, tabular):
            _, (last, _) = self.local(sequence[:, -self.short_length:])
            local = last[-1]
            context = self.long(self.projection(sequence[:, :-self.short_length]) + self.position)
            query = local.unsqueeze(1)
            attended, _ = self.cross(query, context, context, need_weights=False)
            fused = self.cross_norm(query + attended)
            fused = self.ffn_norm(fused + self.ffn(fused)).squeeze(1)
            gate = torch.sigmoid(self.gate(local))
            combined = gate * fused + (1 - gate) * local
            return self.output(torch.cat((combined, tabular), dim=-1)).squeeze(-1)

    return {"dlinear": DLinear, "lstm": SmallLSTM, "transformer": SmallTransformer,
            "gated_lstm_transformer": GatedLSTMTransformer}[name]()


def _arrays(arrays, cfg, targets=False, allow_empty=False):
    np, _ = _dependencies()
    if not isinstance(arrays, dict) or "sequence" not in arrays or "tabular" not in arrays:
        raise ValueError("arrays must contain sequence and tabular")
    sequence = np.asarray(arrays["sequence"], dtype=np.float32)
    tabular = np.asarray(arrays["tabular"], dtype=np.float32)
    if sequence.ndim != 3 or tuple(sequence.shape[1:]) != (cfg["sequence_length"], cfg["sequence_dim"]):
        raise ValueError(f"Wrong sequence shape {sequence.shape}")
    if tabular.ndim != 2 or tuple(tabular.shape) != (len(sequence), cfg["tabular_dim"]):
        raise ValueError(f"Wrong tabular shape {tabular.shape}")
    if not allow_empty and len(sequence) == 0:
        raise ValueError("Training and validation arrays must be nonempty")
    if not np.isfinite(sequence).all() or not np.isfinite(tabular).all():
        raise ValueError("Neural input contains NaN/Inf; apply the saved train-only imputer/scaler and missing masks first")
    result = [np.ascontiguousarray(sequence), np.ascontiguousarray(tabular)]
    if targets:
        keys = [key for key in ("target", "y_return_7d", "y") if key in arrays]
        if not keys:
            raise ValueError("Training arrays require target (+7d return)")
        target = np.asarray(arrays[keys[0]], dtype=np.float32).reshape(-1)
        if len(target) != len(sequence) or not np.isfinite(target).all():
            raise ValueError("Target must be a finite return vector matching inputs")
        for key in keys[1:]:
            if not np.array_equal(target, np.asarray(arrays[key], dtype=np.float32).reshape(-1)):
                raise ValueError("Conflicting target aliases")
        result.append(np.ascontiguousarray(target))
    return result


def _loader(values, batch_size, shuffle, seed, cuda):
    _, torch = _dependencies()
    tensors = tuple(torch.from_numpy(value) for value in values)
    generator = torch.Generator().manual_seed(seed)
    return torch.utils.data.DataLoader(torch.utils.data.TensorDataset(*tensors),
        batch_size=batch_size, shuffle=shuffle, num_workers=0, pin_memory=cuda,
        generator=generator, drop_last=False)


def _autocast(torch, cuda):
    # CUDA AMP for the user's torch 2.0.1 as well as current torch releases.
    return torch.autocast(device_type="cuda", dtype=torch.float16) if cuda else nullcontext()


def _scaler(torch, cuda):
    if hasattr(torch, "amp") and hasattr(torch.amp, "GradScaler"):
        return torch.amp.GradScaler("cuda", enabled=cuda)
    return torch.cuda.amp.GradScaler(enabled=cuda)


def _predict_loaded(network, arrays, cfg, device, batch_size):
    np, torch = _dependencies()
    values = _arrays(arrays, cfg, allow_empty=True)
    if len(values[0]) == 0:
        return np.empty(0, dtype=np.float32)
    loader = _loader(values, batch_size, False, 0, device.type == "cuda")
    outputs = []
    network.eval()
    with torch.inference_mode():
        for sequence, tabular in loader:
            sequence = sequence.to(device, non_blocking=True)
            tabular = tabular.to(device, non_blocking=True)
            # Evaluation uses float32, independent of CUDA training AMP.
            result = network(sequence, tabular).float()
            if not torch.isfinite(result).all():
                raise FloatingPointError("Model produced a non-finite return")
            outputs.append(result.cpu().numpy())
    return np.concatenate(outputs)


@dataclass
class LoadedNeural:
    """A fitted model; .predict never fits or reads targets."""
    network: object
    config: dict
    metadata: dict
    device: object

    def predict(self, arrays, batch_size=8):
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        return _predict_loaded(self.network, arrays, self.config, self.device, batch_size)


def fit_neural(name, train_arrays, val_arrays, config, output_dir, device="auto"):
    """Fit from train, choose epoch by validation MAE, save local parameters.

    A new output directory is required (an existing empty directory is fine).
    Each completed epoch is journaled. An interruption/error is recorded and
    reraised, never converted into a successful CPU run. A best checkpoint from
    completed epochs is retained but not loadable as a completed experiment.
    """
    np, torch = _dependencies()
    if name not in MODEL_NAMES:
        raise ValueError(f"Unsupported neural model: {name}")
    config = dict(config or {})
    for key, position in (("sequence_length", 1), ("sequence_dim", 2)):
        if key not in config and hasattr(train_arrays.get("sequence"), "shape") and len(train_arrays["sequence"].shape) == 3:
            config[key] = int(train_arrays["sequence"].shape[position])
    if "tabular_dim" not in config and hasattr(train_arrays.get("tabular"), "shape") and len(train_arrays["tabular"].shape) == 2:
        config["tabular_dim"] = int(train_arrays["tabular"].shape[1])
    cfg, train_cfg = _architecture(config), _training_config(config)
    train = _arrays(train_arrays, cfg, targets=True)
    validation = _arrays(val_arrays, cfg, targets=True)
    selected = resolve_device(device)
    cuda = selected.type == "cuda"
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite a nonempty model directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    seed = train_cfg["seed"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if cuda:
        torch.cuda.manual_seed_all(seed)
    # Fixed seed is reproducible within the recorded environment; CUDA floating
    # point kernels/versions are not promised to be bitwise identical everywhere.
    metadata = {
        "version": VERSION, "name": name, "status": "training", "target": "y_return_7d",
        "architecture": cfg, "training": train_cfg, "seed": seed,
        "device_requested": str(device), "device_used": str(selected),
        "device_name": torch.cuda.get_device_name(selected) if cuda else "CPU",
        "torch_version": str(torch.__version__), "cuda_runtime": torch.version.cuda,
        "amp": "cuda_float16" if cuda else "disabled", "train_rows": len(train[0]),
        "validation_rows": len(validation[0]), "selection_metric": "validation_return_mae",
        "weights_file": "best_state.pt", "history_file": "history.json",
        "artifact_dir": str(output), "epochs_completed": 0,
        "preprocessing": "external_train_only_saved_schema_required",
    }
    _write_json(output / "model_config.json", {"name": name, "architecture": cfg, "training": train_cfg})
    _write_json(output / "metadata.json", metadata)
    history = []
    started = time.monotonic()
    try:
        network = build_network(name, cfg).to(selected)
        metadata["parameter_count"] = sum(p.numel() for p in network.parameters())
        optimizer = torch.optim.AdamW(network.parameters(), lr=train_cfg["learning_rate"], weight_decay=train_cfg["weight_decay"])
        scaler = _scaler(torch, cuda)
        train_loader = _loader(train, train_cfg["batch_size"], True, seed, cuda)
        val_loader = _loader(validation, train_cfg["batch_size"], False, seed, cuda)
        best_mae, bad_epochs, best_state = math.inf, 0, None
        for epoch in range(1, train_cfg["epochs"] + 1):
            epoch_started = time.monotonic()
            network.train()
            total_squared, count = 0.0, 0
            for sequence, tabular, target in train_loader:
                sequence, tabular, target = (tensor.to(selected, non_blocking=True) for tensor in (sequence, tabular, target))
                optimizer.zero_grad(set_to_none=True)
                with _autocast(torch, cuda):
                    prediction = network(sequence, tabular)
                    loss = (prediction.float() - target).square().mean()
                if not torch.isfinite(loss):
                    raise FloatingPointError("Non-finite training loss; no fallback or sample deletion performed")
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(network.parameters(), train_cfg["gradient_clip"], error_if_nonfinite=True)
                scaler.step(optimizer)
                scaler.update()
                total_squared += float(loss.detach()) * len(target)
                count += len(target)
            network.eval()
            val_absolute, val_squared, val_count = 0.0, 0.0, 0
            with torch.inference_mode():
                for sequence, tabular, target in val_loader:
                    sequence, tabular, target = (tensor.to(selected, non_blocking=True) for tensor in (sequence, tabular, target))
                    error = network(sequence, tabular).float() - target
                    if not torch.isfinite(error).all():
                        raise FloatingPointError("Non-finite validation prediction")
                    val_absolute += float(error.abs().sum())
                    val_squared += float(error.square().sum())
                    val_count += len(target)
            val_mae = val_absolute / val_count
            row = {"epoch": epoch, "train_return_mse": total_squared / count,
                   "validation_return_mse": val_squared / val_count, "validation_return_mae": val_mae,
                   "seconds": time.monotonic() - epoch_started}
            history.append(row)
            print(f"[{name}] epoch {epoch}/{train_cfg['epochs']} train_mse={row['train_return_mse']:.6g} val_mae={val_mae:.6g}", flush=True)
            if val_mae < best_mae - train_cfg["min_delta"]:
                best_mae, bad_epochs = val_mae, 0
                # A shallow state_dict.copy() still aliases live tensors.
                best_state = {key: value.detach().cpu().clone() for key, value in network.state_dict().items()}
                temporary = output / "best_state.pt.tmp"
                torch.save(best_state, temporary)
                temporary.replace(output / "best_state.pt")
                metadata.update(best_epoch=epoch, validation_return_mae=best_mae)
            else:
                bad_epochs += 1
            metadata["epochs_completed"] = epoch
            _write_json(output / "history.json", history)
            _write_json(output / "metadata.json", metadata)
            if bad_epochs >= train_cfg["patience"]:
                print(f"[{name}] early stop; best epoch {metadata['best_epoch']}", flush=True)
                break
        if best_state is None:
            raise RuntimeError("Training completed without a valid checkpoint")
        metadata.update(status="complete", elapsed_seconds=time.monotonic() - started,
                        stopped_early=len(history) < train_cfg["epochs"], weights_sha256=_sha256(output / "best_state.pt"),
                        config_sha256=_sha256(output / "model_config.json"))
        _write_json(output / "metadata.json", metadata)
        return metadata
    except BaseException as exc:
        metadata.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                        error_type=type(exc).__name__, error=str(exc), elapsed_seconds=time.monotonic() - started)
        _write_json(output / "history.json", history)
        _write_json(output / "metadata.json", metadata)
        if cuda:
            print("[neural] CUDA run stopped; no CPU fallback was attempted.", flush=True)
        raise


def load_neural(artifact_dir, device="auto"):
    """Verify and reload only a completed local state_dict; no refitting."""
    _, torch = _dependencies()
    output = Path(artifact_dir).resolve()
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("version") != VERSION or metadata.get("status") != "complete":
        raise ValueError("Only a complete compatible neural artifact may be loaded")
    # Fixed filenames prevent metadata-controlled path traversal.
    for filename, hash_key in (("best_state.pt", "weights_sha256"), ("model_config.json", "config_sha256")):
        if _sha256(output / filename) != metadata.get(hash_key):
            raise ValueError(f"Saved neural artifact checksum mismatch: {filename}")
    config = json.loads((output / "model_config.json").read_text(encoding="utf-8"))
    cfg = _architecture(config["architecture"])
    if config["name"] != metadata["name"] or cfg != metadata["architecture"]:
        raise ValueError("Saved neural metadata and model configuration disagree")
    selected = resolve_device(device)
    network = build_network(config["name"], cfg)
    state = torch.load(output / "best_state.pt", map_location="cpu", weights_only=True)
    network.load_state_dict(state, strict=True)
    network.to(selected).eval()
    return LoadedNeural(network, cfg, metadata, selected)


def predict_neural(artifact_dir, arrays, device="auto", batch_size=8):
    """Predict +7d returns from saved parameters, without any fit or labels."""
    return load_neural(artifact_dir, device=device).predict(arrays, batch_size=batch_size)
