"""Small synthetic CPU checks; real training/weights/network are never used."""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.research.models import foundation, neural

try:
    import numpy as np
    import torch
    _DEPENDENCIES = True
    _SKIP_REASON = ""
except (ImportError, OSError) as exc:
    _DEPENDENCIES = False
    _SKIP_REASON = f"Optional PyTorch/numpy unavailable: {type(exc).__name__}"


class OptionalImportTests(unittest.TestCase):
    def test_import_never_loads_torch(self):
        root = Path(__file__).resolve().parents[2]
        code = ("import sys; from scripts.research.models import neural, foundation; "
                "assert 'torch' not in sys.modules; print('optional_import_ok')")
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=root,
                                capture_output=True, text=True, check=True)
        self.assertIn("optional_import_ok", result.stdout)


@unittest.skipUnless(_DEPENDENCIES, _SKIP_REASON)
class NeuralAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_threads = torch.get_num_threads()
        torch.set_num_threads(2)
        cls.tmp = tempfile.TemporaryDirectory(prefix="seven_neural_test_")
        cls.root = Path(cls.tmp.name)
        rng = np.random.default_rng(12)
        cls.train = {"sequence": rng.normal(size=(6, 48, 6)).astype("float32"),
                     "tabular": rng.normal(size=(6, 5)).astype("float32"),
                     "target": rng.normal(scale=.1, size=6).astype("float32")}
        cls.validation = {"sequence": rng.normal(size=(3, 48, 6)).astype("float32"),
                          "tabular": rng.normal(size=(3, 5)).astype("float32"),
                          "target": rng.normal(scale=.1, size=3).astype("float32")}
        cls.config = {"epochs": 2, "batch_size": 3, "hidden_dim": 8, "nhead": 2,
                      "short_length": 8, "patience": 2, "dropout": 0., "seed": 17}
        cls.metadata = {}
        try:
            with redirect_stdout(io.StringIO()):
                for name in neural.MODEL_NAMES:
                    cls.metadata[name] = neural.fit_neural(
                        name, cls.train, cls.validation, cls.config, cls.root / name, device="cpu")
        except BaseException:
            cls.tmp.cleanup()
            torch.set_num_threads(cls._old_threads)
            raise

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        torch.set_num_threads(cls._old_threads)

    def test_four_models_save_reload_and_ignore_targets(self):
        # Poisoned future labels demonstrate that inference never accesses them.
        past_only = {**self.validation, "target": object()}
        with patch.object(neural, "fit_neural", side_effect=AssertionError("Inference refitted")):
            for name in neural.MODEL_NAMES:
                with self.subTest(name=name):
                    model_dir = self.root / name
                    first = neural.predict_neural(model_dir, past_only, device="cpu", batch_size=3)
                    loaded = neural.load_neural(model_dir, device="cpu")
                    second = loaded.predict(past_only, batch_size=2)
                    self.assertEqual(first.shape, (3,))
                    self.assertTrue(np.isfinite(first).all())
                    np.testing.assert_allclose(first, second, atol=1e-6, rtol=1e-5)
                    self.assertEqual(self.metadata[name]["status"], "complete")
                    self.assertEqual(self.metadata[name]["architecture"]["sequence_length"], 48)
                    self.assertEqual(self.metadata[name]["amp"], "disabled")
                    self.assertEqual(self.metadata[name]["precision"], "float32")
                    self.assertEqual(self.metadata[name]["optimizer_steps_total"], 4)
                    self.assertEqual(self.metadata[name]["skipped_optimizer_steps_total"], 0)
                    history = json.loads((model_dir / "history.json").read_text())
                    self.assertEqual(len(history), 2)
                    self.assertTrue(all(row["optimizer_steps"] == 2 and row["skipped_optimizer_steps"] == 0
                                        and row["loss_scale"] is None for row in history))

    def test_best_checkpoint_is_independent_of_later_updates(self):
        common = {**self.config, "min_delta": 999.0}
        with redirect_stdout(io.StringIO()):
            neural.fit_neural("lstm", self.train, self.validation, {**common, "epochs": 1}, self.root / "one_epoch", device="cpu")
            result = neural.fit_neural("lstm", self.train, self.validation, {**common, "epochs": 3, "patience": 1}, self.root / "two_epochs", device="cpu")
        self.assertEqual(result["best_epoch"], 1)
        self.assertEqual(result["epochs_completed"], 2)
        self.assertTrue(result["stopped_early"])
        first = torch.load(self.root / "one_epoch/best_state.pt", map_location="cpu", weights_only=True)
        later = torch.load(self.root / "two_epochs/best_state.pt", map_location="cpu", weights_only=True)
        self.assertEqual(set(first), set(later))
        self.assertTrue(all(torch.equal(first[key], later[key]) for key in first))

    def test_refuses_overwrite(self):
        with self.assertRaises(FileExistsError):
            neural.fit_neural("lstm", self.train, self.validation, self.config, self.root / "lstm", device="cpu")

    def test_tampered_checkpoint_rejected_before_torch_load(self):
        import shutil
        copied = self.root / "tampered"
        shutil.copytree(self.root / "lstm", copied)
        with (copied / "best_state.pt").open("ab") as stream:
            stream.write(b"tampered")
        with patch.object(torch, "load", side_effect=AssertionError("Checksum was not checked")):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                neural.load_neural(copied, device="cpu")

    def test_incomplete_and_bad_inputs_are_rejected(self):
        import shutil
        copied = self.root / "incomplete"
        shutil.copytree(self.root / "lstm", copied)
        metadata = json.loads((copied / "metadata.json").read_text())
        metadata["status"] = "interrupted"
        (copied / "metadata.json").write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, "complete"):
            neural.load_neural(copied, device="cpu")
        invalid = {**self.validation, "sequence": self.validation["sequence"].copy()}
        invalid["sequence"][0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "NaN/Inf"):
            neural.predict_neural(self.root / "lstm", invalid, device="cpu")

    def test_device_auto_is_explicit_and_cuda_never_silently_falls_back(self):
        text = io.StringIO()
        with patch.object(torch.cuda, "is_available", return_value=False):
            with redirect_stdout(text):
                selected = neural.resolve_device("auto")
            self.assertEqual(selected.type, "cpu")
            self.assertIn("auto selected CPU", text.getvalue())
            with self.assertRaisesRegex(RuntimeError, "no CPU fallback"):
                neural.resolve_device("cuda")

    def test_precision_defaults_to_float32_and_amp_requires_cuda(self):
        self.assertEqual(neural._training_config()["precision"], "float32")
        self.assertEqual(neural._training_config({"precision": "amp_float16"})["precision"], "amp_float16")
        with self.assertRaisesRegex(ValueError, "precision"):
            neural._training_config({"precision": "float16"})
        output = self.root / "cpu_amp_rejected"
        with self.assertRaisesRegex(ValueError, "requires a CUDA"):
            neural.fit_neural("lstm", self.train, self.validation,
                              {**self.config, "precision": "amp_float16"}, output, device="cpu")
        self.assertFalse(output.exists())

    def test_amp_overflow_skips_and_backs_off_before_any_clipping(self):
        network = torch.nn.Linear(1, 1, bias=False)
        optimizer = torch.optim.SGD(network.parameters(), lr=.1)
        parameter = next(network.parameters())
        before = parameter.detach().clone()

        class ScalerStub:
            """CPU simulation of documented GradScaler found-inf behavior."""
            def __init__(self):
                self.value = 65536.
                self.skipped = 0
                self.updates = 0
            def unscale_(self, optimizer):
                self.found_inf = not bool(torch.isfinite(parameter.grad).all())
            def step(self, optimizer):
                if self.found_inf:
                    self.skipped += 1
                else:
                    optimizer.step()
            def update(self):
                self.updates += 1
                if self.found_inf:
                    self.value /= 2

        scaler = ScalerStub()
        parameter.grad = torch.full_like(parameter, float("inf"))
        with patch.object(torch.nn.utils, "clip_grad_norm_", side_effect=AssertionError("Overflow was clipped before GradScaler recovery")):
            updated = neural._optimizer_step(torch, network, optimizer, scaler, True, 1.)
        self.assertFalse(updated)
        self.assertTrue(torch.equal(before, parameter))
        self.assertEqual((scaler.skipped, scaler.updates, scaler.value), (1, 1, 32768.))
        parameter.grad = torch.full_like(parameter, 2.)
        self.assertTrue(neural._optimizer_step(torch, network, optimizer, scaler, True, 1.))
        self.assertTrue(torch.allclose(parameter, before - .1, atol=1e-6))

    def test_float32_nonfinite_gradients_and_finite_gradient_norm_overflow_stop(self):
        from unittest.mock import Mock
        network = torch.nn.Linear(1, 1, bias=False)
        parameter = next(network.parameters())
        scaler, optimizer = Mock(), Mock()
        parameter.grad = torch.full_like(parameter, float("nan"))
        with self.assertRaisesRegex(FloatingPointError, "float32 gradients"):
            neural._optimizer_step(torch, network, optimizer, scaler, False, 1.)
        scaler.step.assert_not_called()
        scaler.update.assert_not_called()
        parameter.grad = torch.ones_like(parameter)
        with patch.object(torch.nn.utils, "clip_grad_norm_", side_effect=RuntimeError("non-finite norm")):
            with self.assertRaisesRegex(RuntimeError, "non-finite norm"):
                neural._optimizer_step(torch, network, optimizer, scaler, True, 1.)
        scaler.step.assert_not_called()

    def test_epoch_without_successful_steps_fails_without_checkpoint(self):
        output = self.root / "no_optimizer_step"
        with patch.object(neural, "_optimizer_step", return_value=False), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(FloatingPointError, "no successful optimizer steps"):
                neural.fit_neural("lstm", self.train, self.validation, self.config, output, device="cpu")
        metadata = json.loads((output / "metadata.json").read_text())
        self.assertEqual(metadata["status"], "failed")
        self.assertEqual(metadata["optimizer_steps_total"], 0)
        self.assertEqual(metadata["skipped_optimizer_steps_total"], 2)
        self.assertFalse((output / "best_state.pt").exists())


class FoundationLocalVerificationTests(unittest.TestCase):
    def test_download_is_rejected_before_import_or_access(self):
        with self.assertRaisesRegex(ValueError, "local-only"):
            foundation.load_chronos2("not-a-local-directory", {}, allow_download=True)

    def test_manifest_required_and_pickle_weights_rejected(self):
        with tempfile.TemporaryDirectory(prefix="chronos_manifest_test_") as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "trusted mapping"):
                foundation.verify_local_model(root, {})
            (root / "config.json").write_text("{}")
            (root / "model.safetensors").write_bytes(b"synthetic not real weights")
            manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
            resolved, hashes = foundation.verify_local_model(root, manifest)
            self.assertEqual(resolved, root.resolve())
            self.assertEqual(hashes, manifest)
            (root / "model.bin").write_bytes(b"no pickle allowed")
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                foundation.verify_local_model(root, manifest)

    @unittest.skipUnless(_DEPENDENCIES, _SKIP_REASON)
    def test_stub_preserves_missing_and_uses_last_median_without_cross_learning(self):
        captured = []

        class StubPipeline:
            def predict_quantiles(self, **kwargs):
                captured.append(kwargs)
                paths = []
                for _ in kwargs["inputs"]:
                    paths.append(torch.linspace(100, 110, 168).reshape(1, 168, 1))
                return paths, None

        close = np.full((3, 672), 100., dtype=np.float32)
        close[:, 10] = np.nan
        model = foundation.LocalChronos2(StubPipeline(), {"status": "stub_only"})
        result = model.predict(close, [100, 100, 100], batch_size=2)
        np.testing.assert_allclose(result["prediction_return_7d"], [.1, .1, .1])
        self.assertEqual(result["median_path"].shape, (3, 168))
        self.assertEqual(len(captured), 2)
        for call in captured:
            self.assertFalse(call["cross_learning"])
            self.assertEqual(call["prediction_length"], 168)
            self.assertEqual(call["quantile_levels"], [.5])
            self.assertTrue(np.isnan(call["inputs"][:, :, 10]).all())
            self.assertNotIn("future_covariates", call)


if __name__ == "__main__":
    unittest.main()
