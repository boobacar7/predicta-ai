from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from predicta_ml.constants import RANDOM_SEED, default_dataset_path, default_output_dir
from predicta_ml.features.audit import audit_dataset
from predicta_ml.features.dataset import load_football_dataset
from predicta_ml.pipeline import run_benchmark
from predicta_ml.validation.elo_candidate import persist_elo_validation


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    parser = argparse.ArgumentParser(description="PREDICTA football 1X2 ML worker. Dataset 0.3 only.")
    sub = parser.add_subparsers(dest="command", required=True)
    audit_parser = sub.add_parser("audit", help="Audit the frozen football-1x2-history-0.3 parquet.")
    _add_dataset_option(audit_parser)
    bench_parser = sub.add_parser("benchmark", help="Walk-forward baselines, boosting, calibration and registry.")
    _add_dataset_option(bench_parser)
    bench_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for registry artefacts and the JSON report (default: workers/ml/var).",
    )
    validate_parser = sub.add_parser(
        "validate-elo",
        help="Scientific validation of the Elo candidate (no boosting, no production promotion).",
    )
    _add_dataset_option(validate_parser)
    validate_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for the candidate registry and validation JSON.",
    )
    oos_parser = sub.add_parser(
        "oos-backtest",
        help="True temporal OOS backtest of the frozen football-elo-v1-candidate. Does not retune or promote.",
    )
    _add_dataset_option(oos_parser)
    oos_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for provenance and OOS JSON reports (default: workers/ml/reports).",
    )
    args = parser.parse_args(argv)
    dataset_path = _resolve_dataset(args.dataset)
    if args.command == "audit":
        report = audit_dataset(load_football_dataset(dataset_path))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if args.command == "oos-backtest":
        from predicta_ml.constants import default_committed_reports_dir
        from predicta_ml.oos.runner import run_from_paths, write_reports

        run = run_from_paths(dataset_path)
        paths = write_reports(run, output_dir=args.output_dir or default_committed_reports_dir())
        print(
            json.dumps(
                {
                    "verdict": run.report["verdict"],
                    "candidate_promoted": False,
                    "window": run.report["window"],
                    "prediction": {
                        "n": run.report["prediction"]["n"],
                        "log_loss": run.report["prediction"]["log_loss"],
                        "brier_score": run.report["prediction"]["brier_score"],
                        "ece": run.report["prediction"]["ece"],
                        "accuracy": run.report["prediction"]["accuracy"],
                    },
                    "odds": run.report["odds"],
                    "ai_picks": {
                        "n_picks": run.report["ai_picks"]["n_picks"],
                        "sample_note": run.report["ai_picks"]["sample_note"],
                    },
                    "paths": paths,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    output_dir = args.output_dir or default_output_dir()
    if args.command == "validate-elo":
        report = persist_elo_validation(dataset_path, output_dir=output_dir)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "promoted_to_production": report["promoted_to_production"],
                    "model_version": report["model_version"],
                    "walk_forward": report["walk_forward"],
                    "calibration": {
                        "chosen": report["calibration"]["chosen_on_calibration_select"],
                        "sigmoid_improves_test": report["calibration"]["sigmoid_improves_test_log_loss"],
                        "test": report["test"],
                    },
                    "sensitivity_candidate": report["sensitivity"]["candidate"],
                    "report_path": report["report_path"],
                    "registry": report["registry"],
                    "reload_matches": report["reload_matches"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    report = run_benchmark(dataset_path, output_dir=output_dir)
    print(
        json.dumps(
            {
                "selected_model": report["selected_model"],
                "test": report["test"]["selected_metrics"],
                "ensemble_used": report["ensemble"]["used"],
                "report_path": report["report_path"],
                "registry": report["registry"],
                "random_seed": RANDOM_SEED,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _add_dataset_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Path to football-1x2-history-0.3 parquet.",
    )


def _resolve_dataset(cli_path: Path | None) -> Path:
    if cli_path is not None:
        return cli_path
    env_path = os.environ.get("PREDICTA_ML_DATASET", "").strip()
    if env_path:
        return Path(env_path)
    return default_dataset_path()
