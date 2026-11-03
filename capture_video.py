
import csv
import sys
from pathlib import Path

import qscript


def main(csv_path: str, video_folder: str | None = None) -> int:
    if video_folder:
        qscript.PATH_TO_VIDEO_FOLDER = video_folder

    Path(qscript.PATH_TO_VIDEO_FOLDER).resolve().mkdir(parents=True, exist_ok=True)

    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"CSV not found: {csv_file}", file=sys.stderr)
        return 1

    ok = 0
    with csv_file.open("r", encoding="utf-8", newline="") as f:
        # Ровно как в ТЗ
        reader = csv.DictReader(f, delimiter=";", quotechar='"')
        for i, row in enumerate(reader, start=1):
            print(f"[{i}] {row.get('Company Name')} @ {row.get('City')}")
            result = qscript.CaptureVideo_Magento(
                url=row["URL"],
                company_name=row["Company Name"],
                language=row["Language"],
                country=row["Country"],
                postcode=row["Postcode"],
                city=row["City"],
                street=row["Street"],
                house_no=row["HouseNo"],
            )
            if result:
                print(f"    saved -> {result}")
                ok += 1
            else:
                print("    FAILED")

    print(f"Done. {ok} video(s) recorded.")
    return 0 if ok else 1


if __name__ == "__main__":
    csv_arg = sys.argv[1] if len(sys.argv) > 1 else "input.csv"
    video_arg = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(main(csv_arg, video_arg))