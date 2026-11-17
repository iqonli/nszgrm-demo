#!/usr/bin/env python3
"""Prepare NSZGRM static files from archived and standalone JSON models."""

from __future__ import annotations
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "model"
PUBLISH_DIR = ROOT / "public"
REQUIRED_MODELS = ("models_int8.json", "models_fp32.json")
MAX_NESTED_ARCHIVES = 5

TAR_SUFFIXES = (
    ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz", ".tbz2",
    ".tar.xz", ".txz", ".tar.zst", ".tzst", ".tar.lzma",
    ".tar.lz", ".tar.z", ".taz", ".tar.lzo",
)
SEVEN_ZIP_SUFFIXES = (".7z", ".zip", ".rar")
added = {}
skipped = 0
archives = 0


def archive_kind(filename: str) -> str | None:
    name = filename.lower()
    if name.endswith(TAR_SUFFIXES):
        return "tar"
    if name.endswith(SEVEN_ZIP_SUFFIXES):
        return "7z"
    return None


def place_json(source: Path, origin: str) -> None:
    global skipped
    if source.is_symlink() or not source.is_file():
        return
    dest = PUBLISH_DIR / source.name
    if dest.exists():
        skipped += 1
        print(f"SKIP {source.name}: already provided by {added.get(source.name, 'output')}")
        return
    if source.stat().st_size == 0:
        raise RuntimeError(f"Empty model JSON: {origin}")
    partial = dest.with_name(dest.name + ".partial")
    try:
        with source.open("rb") as incoming, partial.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
        partial.replace(dest)
    finally:
        partial.unlink(missing_ok=True)
    added[source.name] = origin
    print(f"ADD  {source.name}: {dest.stat().st_size:,} bytes <- {origin}")


def process_tar(archive: Path, depth: int, origin: str) -> None:
    global skipped
    # Read members through tar stdout; stored paths are never written to disk.
    listing = subprocess.run(["tar", "-tf", str(archive)], capture_output=True)
    if listing.returncode:
        raise RuntimeError(
            f"GNU tar cannot list {origin}: "
            f"{listing.stderr.decode(errors='replace').strip()}"
        )
    seen = set()
    members = []
    for member in listing.stdout.decode("utf-8", "surrogateescape").splitlines():
        if member in seen:
            continue
        seen.add(member)
        basename = PurePosixPath(member).name
        if basename.lower().endswith(".json") or archive_kind(basename):
            members.append((member, basename))
    members.sort(key=lambda pair: (not pair[1].lower().endswith(".json"), pair[0]))

    with tempfile.TemporaryDirectory(prefix="nszgrm-tar-") as tempdir:
        for index, (member, basename) in enumerate(members):
            if basename.lower().endswith(".json") and (PUBLISH_DIR / basename).exists():
                skipped += 1
                print(f"SKIP {basename}: already provided")
                continue
            output = Path(tempdir) / f"member-{index:05d}"
            with output.open("wb") as stream:
                result = subprocess.run(
                    ["tar", "--occurrence=1", "-xOf", str(archive), "--", member],
                    stdout=stream, stderr=subprocess.PIPE,
                )
            if result.returncode:
                raise RuntimeError(
                    f"Cannot extract {member} from {origin}: "
                    f"{result.stderr.decode(errors='replace').strip()}"
                )
            named = output.with_name(basename)
            output.rename(named)
            if basename.lower().endswith(".json"):
                place_json(named, f"{origin}!/{member}")
            elif archive_kind(basename):
                process_archive(named, depth + 1, f"{origin}!/{member}")


def process_seven_zip(archive: Path, depth: int, origin: str) -> None:
    binary = os.environ.get("SEVEN_ZIP") or shutil.which("7zz") or shutil.which("7z")
    if not binary:
        raise RuntimeError("7zz is required for ZIP/7z/RAR; run bash build.sh")
    with tempfile.TemporaryDirectory(prefix="nszgrm-7z-") as tempdir:
        result = subprocess.run(
            [binary, "x", "-y", "-bd", "-aos", f"-o{tempdir}", str(archive)],
            capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(
                f"7zz cannot extract {origin}: "
                f"{result.stderr.decode(errors='replace').strip()} "
                f"{result.stdout.decode(errors='replace')[-500:]}"
            )
        folder = Path(tempdir)
        files = sorted(
            (path for path in folder.rglob("*")
             if path.is_file() and not path.is_symlink()),
            key=lambda path: path.relative_to(folder).as_posix(),
        )
        for path in files:
            if path.name.lower().endswith(".json"):
                place_json(path, f"{origin}!/{path.relative_to(folder).as_posix()}")
        for path in files:
            if archive_kind(path.name):
                process_archive(
                    path, depth + 1, f"{origin}!/{path.relative_to(folder).as_posix()}"
                )


def process_archive(path: Path, depth: int, origin: str) -> None:
    global archives
    if depth > MAX_NESTED_ARCHIVES:
        raise RuntimeError(f"Archive nesting exceeds {MAX_NESTED_ARCHIVES}: {origin}")
    kind = archive_kind(path.name)
    if kind is None:
        return
    archives += 1
    print(f"OPEN {origin}")
    if kind == "tar":
        process_tar(path, depth, origin)
    else:
        process_seven_zip(path, depth, origin)


def main() -> None:
    if not (ROOT / "index.html").is_file():
        raise RuntimeError("Missing index.html")
    if not MODEL_DIR.is_dir():
        raise RuntimeError("Missing model/ directory")
    if PUBLISH_DIR.exists():
        shutil.rmtree(PUBLISH_DIR)
    PUBLISH_DIR.mkdir()
    shutil.copy2(ROOT / "index.html", PUBLISH_DIR / "index.html")
    files = sorted(
        (path for path in MODEL_DIR.rglob("*")
         if path.is_file() and not path.is_symlink()),
        key=lambda path: path.relative_to(MODEL_DIR).as_posix(),
    )
    # Prefer standalone JSON files; process archives in lexical path order.
    for path in files:
        if path.name.lower().endswith(".json"):
            place_json(path, path.relative_to(ROOT).as_posix())
    for path in files:
        if archive_kind(path.name):
            process_archive(path, 0, path.relative_to(ROOT).as_posix())
    missing = [name for name in REQUIRED_MODELS if name not in added]
    if missing:
        raise RuntimeError("Missing required JSON models: " + ", ".join(missing))
    print(f"DONE: {len(added)} JSON, {archives} archives, {skipped} skipped duplicates")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"BUILD FAILED: {error}", file=sys.stderr)
        sys.exit(1)
