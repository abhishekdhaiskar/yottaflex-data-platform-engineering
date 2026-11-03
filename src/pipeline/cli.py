
import argparse

from src.pipeline.ingest import run_ingestion
from src.pipeline.replay import run_replay


def main():
    parser = argparse.ArgumentParser(
        description="YottaFlex Data Engineering Pipeline"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest an orders CSV file"
    )
    ingest_parser.add_argument(
        "--file",
        required=True
    )

    replay_parser = subparsers.add_parser(
        "replay",
        help="Replay corrected quarantined records"
    )
    replay_parser.add_argument(
        "--file",
        required=True
    )

    args = parser.parse_args()

    if args.command == "ingest":
        run_ingestion(args.file)

    elif args.command == "replay":
        run_replay(args.file)


if __name__ == "__main__":
    main()
