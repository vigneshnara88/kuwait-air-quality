"""Local file-based analysis commands; inputs and outputs remain user-controlled."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from . import __version__
from .data import missingness_tables, parse_timestamp, read_panel
from .evaluation import evaluate_idw
from .models import fit_regressions
from .spatial import StationNetwork, fill_idw


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kuwait PM2.5 preparation and statistical modelling.")
    commands = parser.add_subparsers(dest="command", required=True)
    missing = commands.add_parser("missingness", help="Summarize missing rows and contiguous hourly gaps.")
    impute = commands.add_parser("idw", help="Fill missing values from observed same-time neighbours.")
    evaluate = commands.add_parser("evaluate-idw", help="Hide observed contiguous-hour blocks and score IDW.")
    regress = commands.add_parser("regress", help="Fit OLS/HC3 and quantile models before a time cutoff.")
    for command in (missing, impute, evaluate, regress):
        command.add_argument("--data", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True, help="New output directory.")
    for command in (impute, evaluate):
        command.add_argument("--stations", type=Path, required=True)
        command.add_argument("--power", type=float, default=1.0)
        command.add_argument("--neighbors", type=int, default=7, help="Nearest observed stations; 0 uses all.")
    evaluate.add_argument("--start", required=True, help="Inclusive start, with timezone offset.")
    evaluate.add_argument("--end", required=True, help="Exclusive end, with timezone offset.")
    evaluate.add_argument("--outage-hours", type=int, default=168)
    evaluate.add_argument("--blocks-per-station", type=int, default=3)
    evaluate.add_argument("--seed", type=int, default=42)
    regress.add_argument("--train-before", required=True, help="Exclusive fitting cutoff, with timezone offset.")
    regress.add_argument("--features", nargs="+", required=True)
    regress.add_argument("--quantiles", type=float, nargs="+", default=[0.1, 0.5, 0.9])
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Choose a new output directory; an existing path will not be overwritten.")
        panel = read_panel(args.data)
        metadata = {
            "command": args.command, "package_version": __version__,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_file": args.data.name, "rows": len(panel),
            "stations": int(panel["station_id"].nunique()),
        }
        tables = {}
        if args.command == "missingness":
            tables["station_missingness.csv"], tables["missing_runs.csv"] = missingness_tables(panel)
            metadata["denominator"] = "recorded rows; scheduled missing rows must be supplied explicitly"
        elif args.command in {"idw", "evaluate-idw"}:
            network = StationNetwork.from_csv(args.stations)
            neighbors = None if args.neighbors == 0 else args.neighbors
            metadata.update({"station_file": args.stations.name, "power": args.power, "neighbors": neighbors})
            if args.command == "idw":
                result = fill_idw(panel, network, power=args.power, neighbors=neighbors)
                tables["imputed_panel.csv"] = result
                metadata.update({
                    "original_missing": int(result["pm25"].isna().sum()),
                    "filled": int(result["was_imputed"].sum()),
                    "remaining_missing": int(result["pm25_idw"].isna().sum()),
                })
            else:
                result, details = evaluate_idw(
                    panel, network, start=parse_timestamp(args.start), end=parse_timestamp(args.end),
                    hours=args.outage_hours, blocks_per_station=args.blocks_per_station,
                    seed=args.seed, power=args.power, neighbors=neighbors,
                )
                tables["masked_predictions.csv"] = result
                metadata.update(details)
        else:
            coefficients, predictions, details = fit_regressions(
                panel, predictors=args.features, train_before=parse_timestamp(args.train_before),
                quantiles=tuple(args.quantiles),
            )
            tables["coefficients.csv"] = coefficients
            tables["held_out_predictions.csv"] = predictions
            metadata.update(details)
        metadata_text = json.dumps(metadata, indent=2, allow_nan=False) + "\n"
        args.output.mkdir(parents=True, exist_ok=False)
        for filename, frame in tables.items():
            frame.to_csv(args.output / filename, index=False)
        (args.output / "metadata.json").write_text(metadata_text, encoding="utf-8")
        print(f"Wrote {len(tables)} CSV file(s) and metadata to {args.output}")
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
