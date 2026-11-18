#!/usr/bin/env bash
# Download a pinned oasdiff release into ./.bin (used locally via `make tools` and in CI).
set -euo pipefail

VERSION="${OASDIFF_VERSION:-1.37.0}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/.bin"

case "$(uname -s)" in
  Linux)  os=linux ;;
  Darwin) os=darwin ;;
  *) echo "unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64|amd64)  arch=amd64 ;;
  arm64|aarch64) arch=arm64 ;;
  *) echo "unsupported arch: $(uname -m)" >&2; exit 1 ;;
esac
[ "$os" = darwin ] && arch=all

if [ -x "$DEST/oasdiff" ] && "$DEST/oasdiff" --version | grep -q "$VERSION"; then
  echo "oasdiff $VERSION already installed in $DEST"; exit 0
fi

url="https://github.com/oasdiff/oasdiff/releases/download/v${VERSION}/oasdiff_${VERSION}_${os}_${arch}.tar.gz"
echo "downloading $url"
mkdir -p "$DEST"
curl -fsSL "$url" | tar -xz -C "$DEST" oasdiff
"$DEST/oasdiff" --version
