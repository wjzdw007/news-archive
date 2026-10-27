#!/usr/bin/env bash
# Pack / restore the archive SQLite that lives on the orphan `data` branch.
#
# GitHub rejects a single blob > 100 MiB (run 40500314784: 100.75 MiB raw
# sqlite). VACUUM on the live DB only reclaimed ~3 MiB. This script:
#   pack    — VACUUM a copy, gzip -9, split at 90 MiB if needed
#   restore — gunzip (+ concat parts), with a fallback to the legacy raw blob
#
# Usage:
#   scripts/data_branch_archive.sh restore DEST_SQLITE
#   scripts/data_branch_archive.sh pack SQLITE OUT_DIR
#
# Env:
#   ARCHIVE_DATA_REF     git ref that holds the data-branch tree (default: data)
#   ARCHIVE_SPLIT_BYTES  split threshold (default: 90 MiB)
set -euo pipefail

GITHUB_BLOB_LIMIT=104857600   # 100 MiB — GitHub pre-receive hard limit
DEFAULT_SPLIT_BYTES=94371840  # 90 MiB — leave headroom under the hard limit
RAW_BLOB="data/archive.sqlite3"
GZ_BLOB="data/archive.sqlite3.gz"
PART_PREFIX="data/archive.sqlite3.gz."

file_size() {
  if stat -c%s "$1" >/dev/null 2>&1; then
    stat -c%s "$1"
  else
    stat -f%z "$1"
  fi
}

human_bytes() {
  python3 -c "print(f'{int($1)/1024/1024:.2f}MiB')"
}

die() {
  echo "❌ $*" >&2
  exit 1
}

list_part_paths() {
  local ref="$1"
  git ls-tree -r --name-only "$ref" \
    | grep -E "^${PART_PREFIX}[0-9]+$" \
    | sort
}

unpack_stream_to() {
  local dest="$1"
  local tmp="${dest}.unpack.$$"
  gzip -dc > "$tmp"
  if ! sqlite3 "$tmp" "PRAGMA integrity_check;" | grep -qx ok; then
    rm -f "$tmp"
    echo "❌ restored sqlite failed integrity_check" >&2
    exit 2
  fi
  mv -f "$tmp" "$dest"
}

cmd_restore() {
  local dest="${1:-}"
  local ref="${ARCHIVE_DATA_REF:-data}"
  [ -n "$dest" ] || die "restore requires DEST sqlite path"

  mkdir -p "$(dirname "$dest")"

  if git cat-file -e "${ref}:${GZ_BLOB}" 2>/dev/null; then
    echo "Restoring ${ref}:${GZ_BLOB} (gzip)"
    git show "${ref}:${GZ_BLOB}" | unpack_stream_to "$dest"
  else
    local parts
    parts="$(list_part_paths "$ref" || true)"
    if [ -n "$parts" ]; then
      echo "Restoring split gzip parts from ${ref}:"
      echo "$parts"
      local concat
      concat="$(mktemp)"
      while IFS= read -r part; do
        [ -n "$part" ] || continue
        git show "${ref}:${part}" >> "$concat"
      done <<< "$parts"
      unpack_stream_to "$dest" < "$concat"
      rm -f "$concat"
    elif git cat-file -e "${ref}:${RAW_BLOB}" 2>/dev/null; then
      echo "Restoring legacy ${ref}:${RAW_BLOB} (uncompressed)"
      local tmp="${dest}.unpack.$$"
      git show "${ref}:${RAW_BLOB}" > "$tmp"
      if ! sqlite3 "$tmp" "PRAGMA integrity_check;" | grep -qx ok; then
        rm -f "$tmp"
        echo "❌ legacy sqlite failed integrity_check" >&2
        exit 2
      fi
      mv -f "$tmp" "$dest"
    else
      die "no archive payload on ${ref} (${GZ_BLOB} / ${PART_PREFIX}* / ${RAW_BLOB})"
    fi
  fi

  echo "✓ Restored $(human_bytes "$(file_size "$dest")") -> ${dest}"
}

cmd_pack() {
  local src="${1:-}"
  local out="${2:-}"
  [ -n "$src" ] && [ -f "$src" ] || die "pack requires an existing SQLITE path"
  [ -n "$out" ] || die "pack requires OUT_DIR"

  local split_bytes="${ARCHIVE_SPLIT_BYTES:-$DEFAULT_SPLIT_BYTES}"
  mkdir -p "$out"
  rm -f "$out"/archive.sqlite3.gz "$out"/archive.sqlite3.gz.* "$out"/PACK_META.json

  local raw_bytes vacuum_bytes packed_bytes
  raw_bytes="$(file_size "$src")"

  local work
  work="$(mktemp)"
  cp "$src" "$work"
  sqlite3 "$work" "VACUUM;"
  vacuum_bytes="$(file_size "$work")"

  local gz="$out/archive.sqlite3.gz"
  gzip -9 -c "$work" > "$gz"
  rm -f "$work"
  packed_bytes="$(file_size "$gz")"

  local files_json split="false"
  if [ "$packed_bytes" -gt "$split_bytes" ]; then
    split="true"
    split -b "$split_bytes" -d -a 3 "$gz" "$out/archive.sqlite3.gz."
    rm -f "$gz"
    local part names=()
    for part in "$out"/archive.sqlite3.gz.[0-9][0-9][0-9]; do
      [ -f "$part" ] || continue
      local psz
      psz="$(file_size "$part")"
      if [ "$psz" -ge "$GITHUB_BLOB_LIMIT" ]; then
        die "packed part $(basename "$part") is $(human_bytes "$psz") (>= 100MiB GitHub limit)"
      fi
      names+=("$(basename "$part")")
    done
    files_json="$(python3 -c "import json,sys; print(json.dumps(sys.argv[1:]))" "${names[@]}")"
  else
    if [ "$packed_bytes" -ge "$GITHUB_BLOB_LIMIT" ]; then
      die "packed gzip is $(human_bytes "$packed_bytes") (>= 100MiB GitHub limit)"
    fi
    files_json='["archive.sqlite3.gz"]'
  fi

  python3 - "$out/PACK_META.json" "$raw_bytes" "$vacuum_bytes" "$packed_bytes" "$split" "$files_json" <<'PY'
import json, sys
path, raw, vac, packed, split, files_json = sys.argv[1:7]
meta = {
    "raw_bytes": int(raw),
    "vacuum_bytes": int(vac),
    "packed_bytes": int(packed),
    "split": split == "true",
    "files": json.loads(files_json),
}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(meta, fh, indent=2)
    fh.write("\n")
PY

  echo "✓ Packed $(human_bytes "$raw_bytes") raw / $(human_bytes "$vacuum_bytes") vacuum -> $(human_bytes "$packed_bytes") gzip-9 (split=${split})"
  echo "  files: ${files_json}"
}

case "${1:-}" in
  restore)
    shift
    cmd_restore "$@"
    ;;
  pack)
    shift
    cmd_pack "$@"
    ;;
  *)
    die "usage: $0 restore DEST | pack SQLITE OUT_DIR"
    ;;
esac
