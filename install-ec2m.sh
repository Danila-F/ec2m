#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ec2m"
DEFAULT_PREFIX="/usr/local"
USER_PREFIX="${HOME}/.local"

log() {
  printf '[ec2m-install] %s\n' "$*"
}

have() {
  command -v "$1" >/dev/null 2>&1
}

INSTALL_MODE="install"

run_pkg_root() {
  if [[ -n "${PKG_SUDO:-}" ]]; then
    "$PKG_SUDO" "$@"
  else
    "$@"
  fi
}

run_install_root() {
  if [[ -n "${INSTALL_SUDO:-}" ]]; then
    "$INSTALL_SUDO" "$@"
  else
    "$@"
  fi
}

init_privilege_helper() {
  if [[ "$(id -u)" -eq 0 ]]; then
    PKG_SUDO=""
  elif have sudo; then
    PKG_SUDO="sudo"
  else
    PKG_SUDO=""
  fi
}

detect_package_manager() {
  if have apt-get; then
    echo apt
  elif have dnf; then
    echo dnf
  elif have yum; then
    echo yum
  elif have zypper; then
    echo zypper
  elif have apk; then
    echo apk
  else
    echo unknown
  fi
}

install_packages() {
  local pm="$1"
  shift
  local packages=("$@")

  if [[ "$(id -u)" -ne 0 && -z "${PKG_SUDO:-}" ]]; then
    log "Need root or sudo to install system packages: ${packages[*]}"
    exit 1
  fi

  case "$pm" in
    apt)
      run_pkg_root apt-get update
      run_pkg_root apt-get install -y "${packages[@]}"
      ;;
    dnf)
      run_pkg_root dnf install -y "${packages[@]}"
      ;;
    yum)
      run_pkg_root yum install -y "${packages[@]}"
      ;;
    zypper)
      run_pkg_root zypper --non-interactive install "${packages[@]}"
      ;;
    apk)
      run_pkg_root apk add --no-cache "${packages[@]}"
      ;;
    *)
      log "Unsupported package manager. Install python3 and python3-pip manually, then rerun."
      exit 1
      ;;
  esac
}

ensure_system_dependencies() {
  local pm
  pm="$(detect_package_manager)"

  if ! have python3; then
    log "python3 not found; installing it"
    case "$pm" in
      apt) install_packages "$pm" python3 python3-pip ca-certificates ;;
      dnf|yum) install_packages "$pm" python3 python3-pip ca-certificates ;;
      zypper) install_packages "$pm" python3 python3-pip ca-certificates ;;
      apk) install_packages "$pm" python3 py3-pip ca-certificates ;;
      *) install_packages "$pm" python3 python3-pip ;;
    esac
  fi

  if ! python3 -m pip --version >/dev/null 2>&1; then
    log "python3-pip not found; installing it"
    case "$pm" in
      apt) install_packages "$pm" python3-pip ;;
      dnf|yum) install_packages "$pm" python3-pip ;;
      zypper) install_packages "$pm" python3-pip ;;
      apk) install_packages "$pm" py3-pip ;;
      *) install_packages "$pm" python3-pip ;;
    esac
  fi
}

uninstall_ec2m() {
  local lib_dir="${INSTALL_LIBDIR:-${PREFIX}/lib/ec2m}"
  local bin_dir="${INSTALL_BINDIR:-${PREFIX}/bin}"
  local wrapper="${bin_dir}/ec2m"
  local alt_wrapper="${bin_dir}/ec2-metrics"

  log "Removing ec2m from ${PREFIX}"
  run_install_root rm -f "$wrapper" "$alt_wrapper"
  run_install_root rm -rf "$lib_dir"
  log "Uninstall complete"
}

choose_prefix() {
  if [[ -n "${INSTALL_PREFIX:-}" ]]; then
    PREFIX="$INSTALL_PREFIX"
    return
  fi

  if [[ "$(id -u)" -eq 0 ]]; then
    PREFIX="$DEFAULT_PREFIX"
    return
  fi

  if [[ -n "${PKG_SUDO:-}" ]]; then
    PREFIX="$DEFAULT_PREFIX"
  else
    PREFIX="$USER_PREFIX"
  fi
}

choose_install_privilege() {
  if [[ "$(id -u)" -eq 0 ]]; then
    INSTALL_SUDO=""
    return
  fi

  case "$PREFIX" in
    "$HOME"/*|"$USER_PREFIX"/*)
      INSTALL_SUDO=""
      return
      ;;
  esac

  if [[ -e "$PREFIX" && -w "$PREFIX" ]]; then
    INSTALL_SUDO=""
    return
  fi

  if [[ -w "$(dirname "$PREFIX")" ]]; then
    INSTALL_SUDO=""
    return
  fi

  if have sudo; then
    INSTALL_SUDO="sudo"
  else
    INSTALL_SUDO=""
  fi
}

print_usage() {
  cat <<'EOF_USAGE'
Usage:
  bash install-ec2m.sh
  bash install-ec2m.sh --uninstall
  curl -fsSL <URL>/install-ec2m.sh | bash

Environment variables:
  INSTALL_PREFIX   Override install root. Default: /usr/local or ~/.local
  INSTALL_BINDIR   Override bin directory
  INSTALL_LIBDIR   Override library directory

Modes:
  default          Install or update ec2m
  --uninstall      Remove ec2m from the selected prefix
  -h, --help       Show this help
EOF_USAGE
}

write_python_app() {
  local target="$1"
  local tmp
  tmp="$(mktemp)"
  python3 - "$tmp" <<'PY_EOF'
import base64
import gzip
import pathlib
import sys

payload = """
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
L/8swYhu8J18jcsG3w809/4fhYbHVNmYAAA=
"""
pathlib.Path(sys.argv[1]).write_bytes(gzip.decompress(base64.b64decode(payload)))
PY_EOF
  run_install_root mkdir -p "$(dirname "$target")"
  run_install_root install -m 0755 "$tmp" "$target"
  rm -f "$tmp"
}

write_wrapper() {
  local wrapper_path="$1"
  local app_py="$2"
  local vendor_dir="$3"
  local tmp
  tmp="$(mktemp)"
  cat >"$tmp" <<EOF_WRAPPER
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${vendor_dir}\${PYTHONPATH:+:\$PYTHONPATH}"
export PYTHONNOUSERSITE=1
exec python3 -s "${app_py}" "\$@"
EOF_WRAPPER
  run_install_root mkdir -p "$(dirname "$wrapper_path")"
  run_install_root install -m 0755 "$tmp" "$wrapper_path"
  rm -f "$tmp"
}

main() {
  init_privilege_helper
  choose_prefix
  choose_install_privilege

  if [[ "$INSTALL_MODE" == "uninstall" ]]; then
    uninstall_ec2m
    return 0
  fi

  ensure_system_dependencies

  local lib_dir="${INSTALL_LIBDIR:-${PREFIX}/lib/ec2m}"
  local bin_dir="${INSTALL_BINDIR:-${PREFIX}/bin}"
  local app_py="${lib_dir}/ec2-metrics.py"
  local vendor_dir="${lib_dir}/vendor"
  local vendor_tmp
  local wrapper="${bin_dir}/ec2m"
  local alt_wrapper="${bin_dir}/ec2-metrics"

  log "Installing into ${PREFIX}"
  run_install_root mkdir -p "$lib_dir" "$vendor_dir" "$bin_dir"

  log "Installing Python dependencies"
  vendor_tmp="$(mktemp -d)"
  run_install_root python3 -m pip install --upgrade --no-cache-dir --target "$vendor_tmp" boto3 botocore
  PYTHONPATH="$vendor_tmp" PYTHONNOUSERSITE=1 python3 -S - <<'PY'
import boto3
import botocore
import s3transfer.compat
PY

  log "Installing application files"
  write_python_app "$app_py"
  run_install_root rm -rf "$vendor_dir"
  run_install_root mkdir -p "$(dirname "$vendor_dir")"
  run_install_root mv "$vendor_tmp" "$vendor_dir"
  write_wrapper "$wrapper" "$app_py" "$vendor_dir"
  if [[ "$alt_wrapper" != "$wrapper" ]]; then
    run_install_root ln -sf "$wrapper" "$alt_wrapper"
  fi

  log "Verifying installation"
  "$wrapper" --help >/dev/null

  log "Installed successfully"
  log "Run: ${wrapper} --help"
  if [[ ":$PATH:" != *":${bin_dir}:"* ]]; then
    log "Note: ${bin_dir} is not in PATH for this shell"
    log "Add it to PATH or run ${wrapper} directly"
  else
    log "Run: ec2m"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --uninstall)
      INSTALL_MODE="uninstall"
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      log "Unknown option: $1"
      print_usage
      exit 1
      ;;
  esac
done

main "$@"
exit 0
