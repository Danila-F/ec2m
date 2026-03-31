#!/usr/bin/env bash
set -euo pipefail

# Installer artifact for ec2m.
# The editable application source lives in src/ec2m.py.

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
H4sIAAAAAAACA819/XfbOJLg7/4reNzXz1K3JEtykknrjfrOcZxu79ixz3Kmb8/R09ISZHNCkVqW
suPx+n+/qsI3CEqWk9wbv+6IxEehUCgUCoVC8d/+x96qyPeu43SPpXfB8qG8zdL9nXixzPIyiPKb
Z3NXTD7HmXz6R5Gl8jkr5FNxuyrjRL2trpd5NmWFzn9Qj2W8UGBXeZLE152c/deKFeXOPM8WwSwq
GZYJRBn53qKaM5aUEX/8Z5ayHQnpOiuzfQ4AH6dZzjrs65QtyzhLCwnrHWQdQtZRnmd5KzhMYpaW
9LKz8/eji9Hx2cdgGIT9bv9Np7vf2e+FOxdHJ0cHo6PJ+4PLI5nX7u63zbzDPw4+fjw6weyijK4T
Fu7s7ByenZ6efZycHl1eHo8mr77j8mno7OT0cXRMcJ52gvgLzz6c3RwctwPByKBEo8vPn8Gasb/
qBB5zEOwJTyER/csj25Z2ArCJcvjbAaJb7rwNmPFNI+XogKCCJIsmgVQagp9DNctC/5xzmZx+S5K
onTKrBbOoq/xYrWwWjjsepq4ZIsoTuP0NsDGpgSw8LfzuUCczVZGZz2lhtATMN0frfJlsioqnVGF
qGClZ3a2hYOd5eDzOU3iRVyyGTA8NSzwCmbspjTAbsKyOL6DucVmu1NDVHTatmkyAoDQ0h2bfvkQ
xYnTjG9ofcxzlD4GwJRBQdCCKYIL5hzextYmpynU+aZBeLNlDGQLXUnT8Q1BFc/RYlGzx45Dk8HdA
8RMrH7L8y2m6O1ucptNsgbPw5rFkNjcIqOercnewUOk22wj2Ipp+YWXxTTgvOYwN4L8NeR/893Hx
5ZJFs3fUsRfgrhgQFhJOniAHeJVG/sxBVzzPVh4AYMlSb2/Ol9/eCvYiyJaFvyffowXsAas0cfJu
9A0DArXrRgGyvmUQNGQf5QXWLyILQvZSW2L8Yqh+Cp+xMgI9KvqUXWVf2Etm7N/70X0vWAg4wTRK
ko1NXLJ/sGn5knVO1gxEm1ZT4ic8/vPoFtUaS2+aLleTFaoak2hZÈvsRZoTwSWlg0B5FagFW0BD
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---_grammar_
