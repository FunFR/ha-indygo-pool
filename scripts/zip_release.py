import os
import zipfile
from pathlib import Path


def create_zip():
    root_dir = Path(__file__).parent.parent
    source_dir = root_dir / "custom_components" / "indygo_pool"
    dist_dir = root_dir / "dist"
    output_zip = dist_dir / "indygo_pool.zip"

    dist_dir.mkdir(exist_ok=True)

    if output_zip.exists():
        os.remove(output_zip)

    print(f"Zipping {source_dir} to {output_zip}...")

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_dir):
            for file in files:
                file_path = Path(root) / file

                if file.endswith(".pyc") or "__pycache__" in str(file_path):
                    continue

                arcname = file_path.relative_to(source_dir)
                zipf.write(file_path, arcname)

    print(f"Successfully created {output_zip}")


if __name__ == "__main__":
    create_zip()
