import json
import random
import shutil
from pathlib import Path
from typing import Dict, List


VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
SOURCE_FOLDERS = [
    "Celeb-DF",
    "Celeb-DF-v2",
    "dfdc_train_part_00",
    "dfdc_train_part_01",
    "dfdc_train_part_49",
]


def list_videos(root: Path) -> List[Path]:
    return [p for p in root.rglob("*") if p.suffix.lower() in VIDEO_EXTS and p.is_file()]


def collect_celeb(folder_root: Path) -> Dict[str, List[Path]]:
    real_dirs = [folder_root / "Celeb-real", folder_root / "YouTube-real"]
    fake_dir = folder_root / "Celeb-synthesis"

    real = []
    for d in real_dirs:
        if d.exists():
            real.extend(list_videos(d))

    fake = list_videos(fake_dir) if fake_dir.exists() else []
    return {"real": real, "fake": fake}


def collect_dfdc(folder_root: Path) -> Dict[str, List[Path]]:
    metadata_files = list(folder_root.rglob("metadata.json"))
    if not metadata_files:
        raise FileNotFoundError(f"No metadata.json found in {folder_root}")

    real, fake = [], []
    for metadata_path in metadata_files:
        with metadata_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)

        video_dir = metadata_path.parent
        for filename, info in meta.items():
            label = str(info.get("label", "")).upper()
            video_path = video_dir / filename
            if not video_path.exists() or video_path.suffix.lower() not in VIDEO_EXTS:
                continue
            if label == "REAL":
                real.append(video_path)
            elif label == "FAKE":
                fake.append(video_path)

    return {"real": real, "fake": fake}


def balanced_fake_sample(
    fake_by_folder: Dict[str, List[Path]], target_total: int, rng: random.Random
) -> List[Path]:
    folders = list(fake_by_folder.keys())
    n = len(folders)
    base_quota = target_total // n
    remainder = target_total % n

    quotas = {f: base_quota for f in folders}
    for f in folders[:remainder]:
        quotas[f] += 1

    selected = []
    deficits = 0
    capacities = {}

    for f in folders:
        available = len(fake_by_folder[f])
        q = quotas[f]
        take = min(available, q)
        selected.extend(rng.sample(fake_by_folder[f], take))
        deficits += q - take
        capacities[f] = max(0, available - take)

    if deficits > 0:
        extra_pool = []
        for f in folders:
            if capacities[f] > 0:
                remaining = [p for p in fake_by_folder[f] if p not in selected]
                extra_pool.extend(remaining)
        if len(extra_pool) < deficits:
            raise RuntimeError(
                f"Not enough fake videos to reach target {target_total}. "
                f"Only {target_total - deficits + len(extra_pool)} available."
            )
        selected.extend(rng.sample(extra_pool, deficits))

    if len(selected) != target_total:
        raise RuntimeError(
            f"Fake selection mismatch: expected {target_total}, got {len(selected)}"
        )
    return selected


def split_items(items: List[Path], rng: random.Random):
    items = list(items)
    rng.shuffle(items)
    n = len(items)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)
    n_test = n - n_train - n_val
    train = items[:n_train]
    val = items[n_train : n_train + n_val]
    test = items[n_train + n_val : n_train + n_val + n_test]
    return train, val, test


def safe_name(src: Path, folder_name: str) -> str:
    rel = str(src).replace(":", "").replace("\\", "_").replace("/", "_")
    return f"{folder_name}__{rel}"


def source_folder_for_path(src: Path) -> str:
    parts = src.parts
    if "dataset_raw" not in parts:
        raise RuntimeError(f"Path does not contain dataset_raw: {src}")
    idx = parts.index("dataset_raw")
    if idx + 1 >= len(parts):
        raise RuntimeError(f"Cannot resolve source folder from path: {src}")
    folder = parts[idx + 1]
    if folder not in SOURCE_FOLDERS:
        raise RuntimeError(f"Unknown source folder '{folder}' from path: {src}")
    return folder


def copy_split(
    files: List[Path], split: str, label: str, out_root: Path, name_set: set, source_folder: str
):
    target_dir = out_root / split / label
    target_dir.mkdir(parents=True, exist_ok=True)

    for src in files:
        name = safe_name(src, source_folder)
        candidate = target_dir / name
        idx = 1
        while str(candidate).lower() in name_set:
            stem = candidate.stem
            suffix = candidate.suffix
            candidate = target_dir / f"{stem}_{idx}{suffix}"
            idx += 1

        shutil.copy2(src, candidate)
        name_set.add(str(candidate).lower())


def main():
    repo_root = Path(__file__).resolve().parents[2]
    dataset_root = repo_root / "dataset_raw"
    out_root = repo_root / "base_deepfake"
    seed = 42
    rng = random.Random(seed)

    if out_root.exists():
        raise FileExistsError(
            f"{out_root} already exists. Remove or rename it before running."
        )

    all_real = []
    fake_by_folder: Dict[str, List[Path]] = {}
    real_by_folder: Dict[str, List[Path]] = {}

    for folder in SOURCE_FOLDERS:
        folder_root = dataset_root / folder
        if not folder_root.exists():
            raise FileNotFoundError(f"Missing source folder: {folder_root}")

        if folder.startswith("Celeb-DF"):
            data = collect_celeb(folder_root)
        else:
            data = collect_dfdc(folder_root)

        all_real.extend(data["real"])
        fake_by_folder[folder] = data["fake"]
        real_by_folder[folder] = data["real"]

    k = len(all_real)
    selected_fakes = balanced_fake_sample(fake_by_folder, k, rng)

    real_train, real_val, real_test = split_items(all_real, rng)
    fake_train, fake_val, fake_test = split_items(selected_fakes, rng)

    used_names = set()

    def by_folder(files):
        m: Dict[str, List[Path]] = {f: [] for f in SOURCE_FOLDERS}
        for p in files:
            m[source_folder_for_path(p)].append(p)
        return m

    for split, files, label in [
        ("train", real_train, "real"),
        ("val", real_val, "real"),
        ("test", real_test, "real"),
        ("train", fake_train, "fake"),
        ("val", fake_val, "fake"),
        ("test", fake_test, "fake"),
    ]:
        grouped = by_folder(files)
        for folder, group in grouped.items():
            copy_split(group, split, label, out_root, used_names, folder)

    fake_selected_by_folder = {f: 0 for f in SOURCE_FOLDERS}
    for p in selected_fakes:
        fake_selected_by_folder[source_folder_for_path(p)] += 1

    summary = {
        "seed": seed,
        "total_real_k": k,
        "total_fake_selected": len(selected_fakes),
        "real_available_by_folder": {f: len(v) for f, v in real_by_folder.items()},
        "fake_available_by_folder": {f: len(v) for f, v in fake_by_folder.items()},
        "fake_selected_by_folder": fake_selected_by_folder,
        "split_counts": {
            "train": {"real": len(real_train), "fake": len(fake_train)},
            "val": {"real": len(real_val), "fake": len(fake_val)},
            "test": {"real": len(real_test), "fake": len(fake_test)},
        },
    }

    with (out_root / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"Created balanced dataset at: {out_root}")


if __name__ == "__main__":
    main()
