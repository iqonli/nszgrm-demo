#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Download 7zz locally, no sudo or GitHub Actions required.
if command -v 7zz >/dev/null 2>&1; then
  export SEVEN_ZIP="$(command -v 7zz)"
elif [[ -x .build-tools/7zz ]]; then
  export SEVEN_ZIP="$PWD/.build-tools/7zz"
else
  if [[ "$(uname -m)" != "x86_64" ]]; then
    echo "The 7zz installer requires Linux x86_64." >&2
    exit 1
  fi
  mkdir -p .build-tools
  archive="$(mktemp)"
  trap 'rm -f "$archive"' EXIT
  curl -fsSL --retry 2 https://www.7-zip.org/a/7z2501-linux-x64.tar.xz -o "$archive"
  echo "4ca3b7c6f2f67866b92622818b58233dc70367be2f36b498eb0bdeaaa44b53f4  $archive" | sha256sum -c -
  tar -xJf "$archive" -C .build-tools 7zz
  chmod +x .build-tools/7zz
  export SEVEN_ZIP="$PWD/.build-tools/7zz"
fi

python3 build.py
