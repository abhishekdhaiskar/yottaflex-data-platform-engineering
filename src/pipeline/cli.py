import argparse
from src.pipeline.ingest import run_ingestion
from src.pipeline.replay import run_replay

def main():
    parser = argparse.ArgumentParser(description="YottaFlex Data Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest and validate CSV orders file")
    ingest_parser.add_argument("--file", required=True, help="Path to input CSV file")

    replay_parser = subparsers.add_parser("replay", help="Replay corrected records")
    replay_parser.add_argument("--file", required=True, help="Path to corrected CSV file")

    args = parser.parse_args()

    if args.command == "ingest":
        run_ingestion(args.file)
    elif args.command == "replay":
        run_replay(args.file)

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()