"""Explicit CLI for local research preparation, fitting, and checkpoint evaluation."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.research.evaluation.seven_training import prepare, train, evaluate, environment, CLASSICAL, NEURAL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("environment")
    prep = commands.add_parser("prepare")
    prep.add_argument("--dataset-id", default="seven_daily_20261020_v1")
    prep.add_argument("--prepared-id")
    prep.add_argument("--profile", choices=("strict", "quality"), default="quality")
    fit = commands.add_parser("train")
    fit.add_argument("--prepared-id", required=True)
    fit.add_argument("--experiment-id")
    fit.add_argument("--models", nargs="+", choices=CLASSICAL + NEURAL, default=list(CLASSICAL))
    fit.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    scoring = commands.add_parser("evaluate")
    scoring.add_argument("--experiment-id", required=True)
    scoring.add_argument("--report-id")
    scoring.add_argument("--split", choices=("validation", "test_exploratory"), default="validation")
    scoring.add_argument("--allow-exploratory-test", action="store_true")
    scoring.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    if args.command == "environment":
        result = environment()
    elif args.command == "prepare":
        result = prepare(args.dataset_id, args.prepared_id, args.profile)
    elif args.command == "train":
        result = train(args.prepared_id, args.models, args.experiment_id, args.device)
    else:
        result = evaluate(args.experiment_id, args.split, args.report_id, args.device, args.allow_exploratory_test)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
