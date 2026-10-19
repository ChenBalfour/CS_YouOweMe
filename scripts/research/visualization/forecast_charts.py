"""Show frozen baseline evaluations without manufacturing future observations.

History uses hour *end* times (source bucket + 3600) so that the reference
close and the daily forecast origin share the same information boundary.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import uuid

VERSION = "forecast-charts-1.1"
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_BASE = ROOT / "data/local/reports/baseline_charts"
CHINA = timezone(timedelta(hours=8))
DAY = 86400
HOUR = 3600


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_bytes(include_predictor):
    """Snapshot the local modules this render can execute, including inits."""
    modules = [Path(__file__).resolve()]
    if include_predictor:
        modules.append(ROOT / "scripts/research/models/baselines.py")
    paths = set(modules)
    for module in modules:
        for parent in module.parents:
            if parent == ROOT:
                break
            initializer = parent / "__init__.py"
            if initializer.is_file():
                paths.add(initializer)
    return {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in sorted(paths)}


def _inside(path, root):
    path = path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Artifact path must remain inside its declared directory")
    return path


def _num(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite price or timestamp")
    return result


def _stamp(value):
    result = _num(value)
    if not result.is_integer() or result <= 0:
        raise ValueError("Timestamp must be a positive integer in seconds")
    return int(result)


def _iso(value):
    return datetime.fromtimestamp(value, CHINA).isoformat()


def _font():
    from matplotlib import font_manager
    available = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"):
        if candidate in available:
            return candidate, True
    return "DejaVu Sans", False


def _broken(times, values, step):
    """Insert a NaN between missing observations; never interpolate."""
    xs, ys = [], []
    for i, (stamp, price) in enumerate(zip(times, values, strict=True)):
        if i and stamp - times[i - 1] > step:
            xs.append(datetime.fromtimestamp(times[i - 1] + step, CHINA))
            ys.append(math.nan)
        xs.append(datetime.fromtimestamp(stamp, CHINA))
        ys.append(price)
    return xs, ys


def _decorate(ax):
    import matplotlib.dates as mdates
    locator = mdates.AutoDateLocator(tz=CHINA, minticks=4, maxticks=9)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz=CHINA))
    ax.grid(True, alpha=0.22)


def _ordered(rows, field):
    rows = sorted(rows, key=lambda row: _stamp(row[field]))
    stamps = [_stamp(row[field]) for row in rows]
    if len(stamps) != len(set(stamps)):
        raise ValueError(f"Duplicate {field} in plot input")
    return rows, stamps


def load_evaluation(manifest):
    """Read and verify the figure inputs from one frozen evaluation manifest.

    No database, API, credential, or notebook output is used as a data source.
    """
    if not isinstance(manifest, dict) or not manifest.get("output_dir"):
        raise ValueError("No saved baseline evaluation; run one offline evaluation first")
    directory = Path(manifest["output_dir"]).resolve()
    tables, inputs = {}, {}
    for key in ("history", "forecast", "test_predictions", "metrics"):
        declared = manifest.get("files", {}).get(key)
        if not isinstance(declared, str):
            raise ValueError(f"Evaluation does not declare {key}")
        path = _inside(directory / declared, directory)
        digest = _sha(path)
        expected = manifest.get("outputs", {}).get(path.relative_to(directory).as_posix(), {})
        if expected.get("sha256") != digest:
            raise ValueError(f"Frozen evaluation hash mismatch: {key}")
        inputs[key] = {"path": str(path), "sha256": digest}
        if key == "metrics":
            tables[key] = json.loads(path.read_text(encoding="utf-8"))
        else:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                tables[key] = list(csv.DictReader(handle))
    tables["manifest"] = manifest
    tables["inputs"] = inputs
    return tables


def projection_data(manifest, origin_time=None, *, loaded=None):
    """Select a past complete sample without changing the selected rule.

    The optional origin is a retrospective display choice. Only sample feature
    fields feed the same fixed rule; labels and future history are not used.
    """
    data = loaded if loaded is not None else load_evaluation(manifest)
    if origin_time is None:
        return {"history": data["history"], "forecast": data["forecast"],
                "inputs": {}, "generated_at": manifest.get("generated_at_beijing")}
    origin_time = _stamp(origin_time)
    parent = manifest.get("input_candidate", {})
    candidate_path = Path(parent["manifest"]).resolve()
    if parent.get("manifest_sha256") != _sha(candidate_path):
        raise ValueError("Candidate manifest hash differs from the evaluated input")
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    directory = candidate_path.parent
    values, inputs = {}, {}
    for filename in ("samples.csv", "source_hourly.csv"):
        path = _inside(directory / filename, directory)
        digest = _sha(path)
        expected = candidate.get("outputs", {}).get(filename, {}).get("sha256")
        if expected != digest:
            raise ValueError(f"Candidate snapshot hash mismatch: {filename}")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            values[filename] = list(csv.DictReader(handle))
        inputs[filename] = {"path": str(path), "sha256": digest}
    sample = next((row for row in values["samples.csv"]
                   if _stamp(row["decision_time"]) == origin_time), None)
    if sample is None or str(sample.get("feature_complete", "")).lower() != "true":
        raise ValueError("Choose an existing daily origin with a complete past feature window")
    from scripts.research.models.baselines import predict_path
    selected = predict_path(sample, manifest["selected_model"])
    persistence = predict_path(sample, "persistence")
    generated = datetime.now(CHINA).isoformat()
    history = [row for row in values["source_hourly.csv"]
               if origin_time - 28 * DAY <= _stamp(row["bucket_time"]) < origin_time]
    forecast = [{"origin_time": origin_time, "target_time": origin_time + day * DAY,
                 "horizon_days": day, "selected_model": manifest["selected_model"],
                 "prediction": selected[day], "persistence_prediction": persistence[day],
                 "generated_at_beijing": generated} for day in range(8)]
    return {"history": history, "forecast": forecast, "inputs": inputs,
            "generated_at": generated}


def plot_holdout(rows, *, selected_model, start_target=None, end_target=None):
    """Actual seven-day targets and forecasts issued seven days earlier.

    Optional bounds are epoch seconds on target_time, both inclusive. Missing
    target dates explicitly break every plotted line.
    """
    import matplotlib.pyplot as plt
    rows, times = _ordered(rows, "target_time")
    rows = [row for row in rows
            if (start_target is None or _stamp(row["target_time"]) >= start_target)
            and (end_target is None or _stamp(row["target_time"]) <= end_target)]
    if not rows:
        raise ValueError("No test targets inside the requested display window")
    times = [_stamp(row["target_time"]) for row in rows]
    if any(_stamp(row["target_time"]) - _stamp(row["origin_time"]) != 7 * DAY for row in rows):
        raise ValueError("Holdout predictions must have a seven-day horizon")
    font, chinese = _font()
    with plt.rc_context({"font.family": font, "axes.unicode_minus": False}):
        fig, (ax, error_ax) = plt.subplots(2, 1, figsize=(12, 7.2), sharex=True,
                                          gridspec_kw={"height_ratios": [3, 1]})
        for field, label, color, style in (
            ("actual", "真实七日目标" if chinese else "Actual seven-day target", "#172b4d", "-"),
            ("prediction", f"选定规则 {selected_model}" if chinese else f"Selected: {selected_model}", "#1468d4", "--"),
            ("persistence_prediction", "不变价基准" if chinese else "Persistence baseline", "#df8c22", ":"),
        ):
            x, y = _broken(times, [_num(row[field]) for row in rows], DAY)
            ax.plot(x, y, label=label, color=color, linestyle=style, linewidth=1.5)
        errors = [_num(row["prediction"]) - _num(row["actual"]) for row in rows]
        x, y = _broken(times, errors, DAY)
        error_ax.plot(x, y, color="#1468d4", linewidth=1.1,
                      label="预测－真实" if chinese else "Forecast minus actual")
        error_ax.axhline(0, color="#64748b", linewidth=0.8)
        ax.set_title("测试留出期：每个预测均来自目标日前七天" if chinese
                     else "Held-out test: each forecast originates seven days before its target")
        ax.set_ylabel("参考价格 / CNY" if chinese else "Reference price / CNY")
        error_ax.set_ylabel("误差 / CNY" if chinese else "Error / CNY")
        error_ax.set_xlabel("目标截止时刻（北京时间）；缺日期断线" if chinese
                            else "Target cutoff (Beijing time); gaps remain disconnected")
        ax.legend(loc="best", fontsize=9)
        error_ax.legend(loc="best", fontsize=8)
        for target in (ax, error_ax):
            _decorate(target)
        fig.tight_layout()
    return fig


def plot_projection(history, forecast, *, lookback_days=28, generated_at=None):
    """Hourly history and the frozen rule's day 0..7 reference path.

    Future real prices are intentionally absent. Day points are straight rule
    projections, not forecasts of intraday fluctuations or confidence bands.
    """
    import matplotlib.pyplot as plt
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) or not 1 <= lookback_days <= 28:
        raise ValueError("lookback_days must be an integer from 1 to 28")
    if not forecast:
        raise ValueError("Forecast table is empty")
    forecast, targets = _ordered(forecast, "target_time")
    origins = {_stamp(row["origin_time"]) for row in forecast}
    if len(origins) != 1:
        raise ValueError("Projection requires a single forecast origin")
    origin = origins.pop()
    horizons = [int(row["horizon_days"]) for row in forecast]
    if horizons != list(range(8)) or any(t != origin + n * DAY for n, t in enumerate(targets)):
        raise ValueError("Projection requires one day 0..7 point at each exact daily horizon")
    history, buckets = _ordered(history, "bucket_time")
    if any(bucket >= origin for bucket in buckets):
        raise ValueError("History must contain only source hours strictly before origin")
    history = [row for row in history if origin - lookback_days * DAY <= _stamp(row["bucket_time"]) < origin]
    if not history:
        raise ValueError("No historical hours inside requested lookback")
    close_times = [_stamp(row["bucket_time"]) + HOUR for row in history]
    if any(stamp > origin for stamp in close_times):
        raise ValueError("An incomplete source hour crosses the forecast origin")
    font, chinese = _font()
    with plt.rc_context({"font.family": font, "axes.unicode_minus": False}):
        fig, ax = plt.subplots(figsize=(12, 5.6))
        x, y = _broken(close_times, [_num(row["close_cny"]) for row in history], HOUR)
        ax.plot(x, y, label="过去小时收盘" if chinese else "Past hourly closes", color="#172b4d", linewidth=1.1)
        points = [datetime.fromtimestamp(target, CHINA) for target in targets]
        model = str(forecast[0]["selected_model"])
        ax.plot(points, [_num(row["prediction"]) for row in forecast], "o--", color="#1468d4",
                label=f"选定规则 {model}" if chinese else f"Selected rule: {model}", markersize=4)
        ax.plot(points, [_num(row["persistence_prediction"]) for row in forecast], "s:", color="#df8c22",
                label="不变价基准" if chinese else "Persistence baseline", markersize=3)
        ax.axvline(datetime.fromtimestamp(origin, CHINA), color="#718096", linestyle="--", linewidth=1,
                   label="回顾预测起点" if chinese else "Retrospective forecast origin")
        title = (f"次时代崭新：过去{lookback_days}天与未来七日日点路径" if chinese
                 else f"Cyrex FN: past {lookback_days} days and projected daily path")
        ax.set_title(title)
        ax.set_ylabel("来源参考价格 / CNY" if chinese else "Source reference price / CNY")
        ax.set_xlabel("北京时间；小时收盘按源bucket+1h绘制" if chinese
                      else "Beijing time; hourly closes shown at source bucket + 1 hour")
        ax.legend(loc="best", fontsize=8)
        _decorate(ax)
        origin_text = _iso(origin)
        generated = generated_at or str(forecast[0].get("generated_at_beijing", "unknown"))
        note = (f"研究起点 {origin_text} | 实际生成 {generated}\n日点间连线仅展示规则路径；未来真实价格未知。回顾示例，非该时刻真实发出预测。" if chinese else
                f"Research origin: {origin_text} | Actually generated: {generated}\nDaily points show rule projections; future actuals are unknown. Retrospective, not a live-issued forecast.")
        fig.text(0.065, 0.015, note, fontsize=8, color="#475569", ha="left", va="bottom")
        fig.tight_layout(rect=(0, 0.09, 1, 1))
    return fig


def figures(manifest, *, lookback_days=28, start_target=None, end_target=None, origin_time=None):
    """Return both figures for immediate display in VS Code; no writes."""
    data = load_evaluation(manifest)
    projection = projection_data(manifest, origin_time, loaded=data)
    return {"holdout": plot_holdout(data["test_predictions"], selected_model=manifest["selected_model"],
                                     start_target=start_target, end_target=end_target),
            "projection": plot_projection(projection["history"], projection["forecast"], lookback_days=lookback_days,
                                           generated_at=projection["generated_at"])}


def render(manifest, output_id=None, *, lookback_days=28, start_target=None, end_target=None, origin_time=None):
    """Save immutable PNGs in a separate report directory and return figures.

    Existing evaluation data, notebooks, and prior chart reports are untouched.
    """
    source_bytes = _source_bytes(include_predictor=origin_time is not None)
    data = load_evaluation(manifest)
    projection = projection_data(manifest, origin_time, loaded=data)
    plots = {"holdout": plot_holdout(data["test_predictions"], selected_model=manifest["selected_model"],
                                    start_target=start_target, end_target=end_target),
             "projection": plot_projection(projection["history"], projection["forecast"], lookback_days=lookback_days,
                                            generated_at=projection["generated_at"])}
    now = datetime.now(CHINA)
    output_id = output_id or f"{manifest['output_id']}_charts_{now.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,150}", output_id):
        raise ValueError("Unsafe chart report identifier")
    directory = _inside(OUTPUT_BASE / output_id, OUTPUT_BASE)
    directory.mkdir(parents=True, exist_ok=False)
    paths = {}
    for key, fig in plots.items():
        path = directory / f"{key}.png"
        fig.savefig(path, dpi=150, facecolor="white")
        paths[key] = str(path)
    for name, content in source_bytes.items():
        if (ROOT / name).read_bytes() != content:
            raise ValueError("Plotting source changed during rendering; report not finalized")
        destination = directory / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    chart_manifest = {"version": VERSION, "output_id": output_id, "output_dir": str(directory),
                      "generated_at_beijing": now.isoformat(), "evaluation_id": manifest["output_id"],
                      "evaluation_generated_at_beijing": manifest.get("generated_at_beijing"),
                      "projection_generated_at_beijing": projection["generated_at"],
                      "inputs": {**data["inputs"], **projection["inputs"]}, "selected_model": manifest["selected_model"],
                      "source_files": {name: {"sha256": hashlib.sha256(content).hexdigest(),
                                               "bytes": len(content)}
                                       for name, content in source_bytes.items()},
                      "parameters": {"lookback_days": lookback_days, "start_target": start_target,
                                     "end_target": end_target, "origin_time": origin_time},
                      "outputs": {p.relative_to(directory).as_posix():
                                  {"sha256": _sha(p), "bytes": p.stat().st_size}
                                  for p in sorted(directory.rglob("*")) if p.is_file()}}
    (directory / "manifest.json").write_text(json.dumps(chart_manifest, ensure_ascii=False, indent=2)
                                              + "\n", encoding="utf-8", newline="\n")
    return {"output_dir": str(directory), "paths": paths, "figures": plots, "manifest": chart_manifest}
