import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game.texture_handler import slice_all_icon_packs


def main():
    parser = argparse.ArgumentParser(description="Slice faction icon sources into per-unit/building PNGs.")
    parser.add_argument("--overwrite", action="store_true", help="Rewrite sliced PNGs even if they already exist.")
    args = parser.parse_args()

    written_paths = slice_all_icon_packs(overwrite=args.overwrite)
    print(f"sliced {len(written_paths)} icon files")
    for path in written_paths:
        print(path)


if __name__ == "__main__":
    main()
