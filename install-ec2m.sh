#!/usr/bin/env bash
set -euo pipefail

# Installer artifact for ec2m.
# The editable application source lives in src/ec2m.py.

APP_NAME="ec2m"
DEFAULT_PREFIX="/usr/local"
USER_PREFIX="${HOME}/.local"
INSTALL_MODE="install"
PKG_SUDO=""
INSTALL_SUDO=""

log() {
  printf '[ec2m-install] %s\n' "$*"
}

have() {
  command -v "$1" >/dev/null 2>&1
}

run_pkg_root() {
  if [[ -n "${PKG_SUDO}" ]]; then
    "${PKG_SUDO}" "$@"
  else
    "$@"
  fi
}

run_install_root() {
  if [[ -n "${INSTALL_SUDO}" ]]; then
    "${INSTALL_SUDO}" "$@"
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

  if [[ "$(id -u)" -ne 0 && -z "${PKG_SUDO}" ]]; then
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

choose_prefix() {
  if [[ -n "${INSTALL_PREFIX:-}" ]]; then
    PREFIX="${INSTALL_PREFIX}"
    return
  fi

  if [[ "$(id -u)" -eq 0 ]]; then
    PREFIX="${DEFAULT_PREFIX}"
    return
  fi

  if [[ -n "${PKG_SUDO}" ]]; then
    PREFIX="${DEFAULT_PREFIX}"
  else
    PREFIX="${USER_PREFIX}"
  fi
}

choose_install_privilege() {
  if [[ "$(id -u)" -eq 0 ]]; then
    INSTALL_SUDO=""
    return
  fi

  case "${PREFIX}" in
    "${HOME}"/*|"${USER_PREFIX}"/*)
      INSTALL_SUDO=""
      return
      ;;
  esac

  if [[ -e "${PREFIX}" && -w "${PREFIX}" ]]; then
    INSTALL_SUDO=""
    return
  fi

  if [[ -w "$(dirname "${PREFIX}")" ]]; then
    INSTALL_SUDO=""
    return
  fi

  if have sudo; then
    INSTALL_SUDO="sudo"
  else
    INSTALL_SUDO=""
  fi
}

uninstall_ec2m() {
  local lib_dir="${INSTALL_LIBDIR:-${PREFIX}/lib/ec2m}"
  local bin_dir="${INSTALL_BINDIR:-${PREFIX}/bin}"
  local wrapper="${bin_dir}/ec2m"
  local alt_wrapper="${bin_dir}/ec2-metrics"

  log "Removing ec2m from ${PREFIX}"
  run_install_root rm -f "${wrapper}" "${alt_wrapper}"
  run_install_root rm -rf "${lib_dir}"
  log "Uninstall complete"
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
E9oPTia4MZlMhI9yZc3l25bm3v8Dj61PpbebAAA=
"""

target = pathlib.Path(sys.argv[1])
source = gzip.decompress(base64.b64decode(payload.encode("ascii")))
target.write_bytes(source)
PY_EOF
  run_install_root mv "${tmp}" "${target}"
  run_install_root chmod 0755 "${target}"
}

install_python_deps() {
  local vendor_dir="$1"
  local cache_dir
  cache_dir="$(mktemp -d)"

  python3 -m pip install \
    --disable-pip-version-check \
    --no-compile \
    --target "${vendor_dir}" \
    --cache-dir "${cache_dir}" \
    --upgrade \
    boto3 \
    botocore

  rm -rf "${cache_dir}"
}

write_wrapper() {
  local target="$1"
  local app_path="$2"
  local vendor_dir="$3"
  local tmp
  tmp="$(mktemp)"

  cat > "${tmp}" <<EOF_WRAPPER
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${vendor_dir}:\${PYTHONPATH:-}"
exec python3 "${app_path}" "\$@"
EOF_WRAPPER

  run_install_root mv "${tmp}" "${target}"
  run_install_root chmod 0755 "${target}"
}

install_ec2m() {
  local lib_dir="${INSTALL_LIBDIR:-${PREFIX}/lib/ec2m}"
  local bin_dir="${INSTALL_BINDIR:-${PREFIX}/bin}"
  local vendor_dir="${lib_dir}/vendor"
  local app_path="${lib_dir}/ec2m.py"

  log "Installing ec2m into ${PREFIX}"
  run_install_root mkdir -p "${bin_dir}" "${lib_dir}" "${vendor_dir}"
  write_python_app "${app_path}"
  install_python_deps "${vendor_dir}"
  write_wrapper "${bin_dir}/ec2m" "${app_path}" "${vendor_dir}"
  write_wrapper "${bin_dir}/ec2-metrics" "${app_path}" "${vendor_dir}"
  log "Install complete"
  log "Command: ${bin_dir}/ec2m"
}

main() {
  init_privilege_helper

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
        log "Unknown argument: $1"
        print_usage
        exit 2
        ;;
    esac
  done

  choose_prefix
  choose_install_privilege

  if [[ "${INSTALL_MODE}" == "uninstall" ]]; then
    uninstall_ec2m
    exit 0
  fi

  ensure_system_dependencies
  install_ec2m
}

main "$@"
