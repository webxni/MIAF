#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${MIAF_REPO_URL:-https://github.com/webxni/MIAF.git}"
REPO_BRANCH="${MIAF_REPO_BRANCH:-main}"
MIAF_HOME="${MIAF_HOME:-$HOME/.miaf}"
REPO_DIR="${MIAF_REPO_DIR:-$MIAF_HOME/repo}"
BIN_DIR="$MIAF_HOME/bin"
ENV_FILE="$REPO_DIR/.env"
ENV_EXAMPLE="$REPO_DIR/.env.example"
APP_BASE_URL="http://localhost"
AUTO_PORTS="${MIAF_AUTO_PORTS:-1}"

log() {
  printf '[miaf-install] %s\n' "$*"
}

warn() {
  printf '[miaf-install] warning: %s\n' "$*" >&2
}

fail() {
  printf '[miaf-install] error: %s\n' "$*" >&2
  exit 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

is_tty() {
  [ -t 0 ] && [ -t 1 ]
}

confirm() {
  local prompt="$1"
  local reply
  if ! is_tty; then
    return 1
  fi
  read -r -p "$prompt [y/N] " reply
  case "$reply" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

require_dependencies() {
  local missing=()

  have_cmd git || missing+=("git")
  have_cmd docker || missing+=("docker")
  have_cmd curl || missing+=("curl")
  if ! docker compose version >/dev/null 2>&1; then
    missing+=("docker compose")
  fi
  if ! have_cmd openssl && ! have_cmd python3 && ! have_cmd python; then
    missing+=("openssl or python3/python")
  fi

  if [ "${#missing[@]}" -gt 0 ]; then
    fail "missing required commands: ${missing[*]}"
  fi
}

detect_platform() {
  local os
  os="$(uname -s)"
  case "$os" in
    Linux|Darwin)
      log "detected platform: $os"
      ;;
    *)
      fail "unsupported platform: $os (expected Linux or macOS)"
      ;;
  esac
}

random_secret() {
  if have_cmd openssl; then
    openssl rand -base64 48 | tr -d '\n' | tr '+/' '-_' | tr -d '='
    return 0
  fi
  if have_cmd python3; then
    python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
    return 0
  fi
  python -c 'import secrets; print(secrets.token_urlsafe(48))'
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  if grep -q "^${key}=" "$file"; then
    sed -i.bak "s|^${key}=.*$|${key}=${value}|" "$file"
    rm -f "${file}.bak"
  else
    printf '%s=%s\n' "$key" "$value" >>"$file"
  fi
}

replace_if_matches() {
  local file="$1"
  local key="$2"
  local expected="$3"
  local replacement="$4"
  if grep -q "^${key}=${expected}$" "$file"; then
    set_env_value "$file" "$key" "$replacement"
  fi
}

bootstrap_env_file() {
  local created_env=0

  if [ ! -f "$ENV_EXAMPLE" ]; then
    fail "missing template env file: $ENV_EXAMPLE"
  fi

  if [ ! -f "$ENV_FILE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    created_env=1
    log "created $ENV_FILE from .env.example"
  else
    log "reusing existing $ENV_FILE"
  fi

  if [ "$created_env" -eq 1 ]; then
    local postgres_password
    local redis_password
    local minio_password
    postgres_password="$(random_secret)"
    redis_password="$(random_secret)"
    minio_password="$(random_secret)"

    set_env_value "$ENV_FILE" "SECRET_KEY" "$(random_secret)"
    set_env_value "$ENV_FILE" "POSTGRES_PASSWORD" "$postgres_password"
    set_env_value "$ENV_FILE" "REDIS_PASSWORD" "$redis_password"
    set_env_value "$ENV_FILE" "MINIO_ROOT_PASSWORD" "$minio_password"
    set_env_value "$ENV_FILE" "MINIO_SECRET_KEY" "$minio_password"
    set_env_value "$ENV_FILE" "AUTOMATION_TOKEN" "$(random_secret)"
    log "generated fresh local secrets in $ENV_FILE"
    return 0
  fi

  if grep -Eq '^(SECRET_KEY|POSTGRES_PASSWORD|REDIS_PASSWORD|MINIO_ROOT_PASSWORD|MINIO_SECRET_KEY|AUTOMATION_TOKEN)=(change-me|replace-with)' "$ENV_FILE"; then
    if confirm "Existing .env still contains placeholder secrets. Replace only the placeholder values now?"; then
      local value
      replace_if_matches "$ENV_FILE" "SECRET_KEY" "change-me-to-a-long-random-string" "$(random_secret)"
      replace_if_matches "$ENV_FILE" "SECRET_KEY" "replace-with-a-long-random-secret" "$(random_secret)"
      replace_if_matches "$ENV_FILE" "POSTGRES_PASSWORD" "change-me-postgres-password" "$(random_secret)"
      replace_if_matches "$ENV_FILE" "POSTGRES_PASSWORD" "replace-with-a-long-random-postgres-password" "$(random_secret)"
      replace_if_matches "$ENV_FILE" "REDIS_PASSWORD" "change-me-redis-password" "$(random_secret)"
      replace_if_matches "$ENV_FILE" "REDIS_PASSWORD" "replace-with-a-long-random-redis-password" "$(random_secret)"

      if grep -Eq '^MINIO_ROOT_PASSWORD=(change-me-minio-password|replace-with-a-long-random-minio-password)$' "$ENV_FILE"; then
        value="$(random_secret)"
        set_env_value "$ENV_FILE" "MINIO_ROOT_PASSWORD" "$value"
        if grep -q '^MINIO_SECRET_KEY=' "$ENV_FILE"; then
          set_env_value "$ENV_FILE" "MINIO_SECRET_KEY" "$value"
        fi
      fi
      if grep -Eq '^MINIO_SECRET_KEY=(change-me-minio-password|replace-with-a-long-random-minio-password)$' "$ENV_FILE"; then
        if grep -q '^MINIO_ROOT_PASSWORD=' "$ENV_FILE"; then
          value="$(awk -F= '$1=="MINIO_ROOT_PASSWORD"{print substr($0, index($0, "=")+1)}' "$ENV_FILE" | tail -n 1)"
        else
          value="$(random_secret)"
          set_env_value "$ENV_FILE" "MINIO_ROOT_PASSWORD" "$value"
        fi
        set_env_value "$ENV_FILE" "MINIO_SECRET_KEY" "$value"
      fi
      replace_if_matches "$ENV_FILE" "AUTOMATION_TOKEN" "change-me-automation-token" "$(random_secret)"
      replace_if_matches "$ENV_FILE" "AUTOMATION_TOKEN" "replace-with-a-long-random-automation-token" "$(random_secret)"
      log "updated placeholder secrets in existing $ENV_FILE"
    else
      warn "existing .env was left unchanged"
    fi
  fi
}

sync_repo() {
  mkdir -p "$MIAF_HOME" "$BIN_DIR"

  if [ ! -d "$REPO_DIR/.git" ]; then
    if [ -e "$REPO_DIR" ]; then
      fail "$REPO_DIR exists but is not a git clone"
    fi
    log "cloning MIAF into $REPO_DIR"
    git clone --branch "$REPO_BRANCH" --single-branch "$REPO_URL" "$REPO_DIR"
    return 0
  fi

  log "updating existing repo in $REPO_DIR"
  git -C "$REPO_DIR" fetch origin "$REPO_BRANCH"
  git -C "$REPO_DIR" checkout "$REPO_BRANCH"
  git -C "$REPO_DIR" pull --ff-only origin "$REPO_BRANCH"
}

install_cli_wrapper() {
  local source_wrapper="$REPO_DIR/bin/miaf"
  local target_wrapper="$BIN_DIR/miaf"

  [ -f "$source_wrapper" ] || fail "missing CLI wrapper: $source_wrapper"
  cp "$source_wrapper" "$target_wrapper"
  chmod +x "$target_wrapper"
  log "installed CLI wrapper at $target_wrapper"
}

wait_for_api_container() {
  local attempts="${1:-60}"
  local i
  for ((i = 1; i <= attempts; i += 1)); do
    if docker compose -f "$REPO_DIR/compose.yaml" exec -T api python -c "print('ok')" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

wait_for_http() {
  local url="$1"
  local attempts="${2:-60}"
  local i
  for ((i = 1; i <= attempts; i += 1)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

configure_urls() {
  local port
  if [ -f "$ENV_FILE" ]; then
    port="$(awk -F= '$1=="HTTP_PORT"{print substr($0, index($0, "=")+1)}' "$ENV_FILE" | tail -n 1)"
    if [ -n "${port:-}" ] && [ "$port" != "80" ]; then
      APP_BASE_URL="http://localhost:$port"
    fi
  fi
}

port_in_use() {
  local port="$1"
  if have_cmd python3; then
    python3 - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("0.0.0.0", port))
except OSError:
    sys.exit(0)
finally:
    try:
        s.close()
    except Exception:
        pass
sys.exit(1)
PY
    return $?
  fi
  if have_cmd python; then
    python - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("0.0.0.0", port))
except OSError:
    sys.exit(0)
finally:
    try:
        s.close()
    except Exception:
        pass
sys.exit(1)
PY
    return $?
  fi
  return 1
}

find_free_port() {
  local start="${1:-20000}"
  local end="${2:-40000}"
  if have_cmd python3; then
    python3 - "$start" "$end" <<'PY'
import random
import socket
import sys

start = int(sys.argv[1])
end = int(sys.argv[2])
ports = list(range(start, end + 1))
random.shuffle(ports)
for port in ports:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
    except OSError:
        pass
    else:
        print(port)
        sys.exit(0)
    finally:
        try:
            s.close()
        except Exception:
            pass
sys.exit(1)
PY
    return $?
  fi
  if have_cmd python; then
    python - "$start" "$end" <<'PY'
import random
import socket
import sys

start = int(sys.argv[1])
end = int(sys.argv[2])
ports = list(range(start, end + 1))
random.shuffle(ports)
for port in ports:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
    except OSError:
        pass
    else:
        print(port)
        sys.exit(0)
    finally:
        try:
            s.close()
        except Exception:
            pass
sys.exit(1)
PY
    return $?
  fi
  return 1
}

ensure_host_ports_available() {
  local http_port https_port
  http_port="$(awk -F= '$1=="HTTP_PORT"{print substr($0, index($0, "=")+1)}' "$ENV_FILE" | tail -n 1)"
  https_port="$(awk -F= '$1=="HTTPS_PORT"{print substr($0, index($0, "=")+1)}' "$ENV_FILE" | tail -n 1)"
  http_port="${http_port:-80}"
  https_port="${https_port:-443}"

  if port_in_use "$http_port"; then
    if [ "$AUTO_PORTS" = "1" ]; then
      http_port="$(find_free_port)" || fail "could not find a free HTTP port automatically"
      set_env_value "$ENV_FILE" "HTTP_PORT" "$http_port"
      warn "host port 80 is busy; using HTTP_PORT=$http_port instead"
    else
      fail "host port $http_port is already in use. Edit $ENV_FILE and set HTTP_PORT to a free port such as 8080, then rerun the installer."
    fi
  fi
  if [ "$https_port" != "$http_port" ] && port_in_use "$https_port"; then
    if [ "$AUTO_PORTS" = "1" ]; then
      https_port="$(find_free_port)" || fail "could not find a free HTTPS port automatically"
      while [ "$https_port" = "$http_port" ]; do
        https_port="$(find_free_port)" || fail "could not find a distinct free HTTPS port automatically"
      done
      set_env_value "$ENV_FILE" "HTTPS_PORT" "$https_port"
      warn "host port 443 is busy; using HTTPS_PORT=$https_port instead"
    else
      fail "host port $https_port is already in use. Edit $ENV_FILE and set HTTPS_PORT to a free port such as 8443, then rerun the installer."
    fi
  fi
  configure_urls
}

run_smoke() {
  log "GET ${APP_BASE_URL}/api/health"
  curl -fsS "${APP_BASE_URL}/api/health" >/dev/null
  log "GET ${APP_BASE_URL}/api/health/ready"
  curl -fsS "${APP_BASE_URL}/api/health/ready" >/dev/null
}

start_stack() {
  configure_urls
  ensure_host_ports_available
  log "building Docker images"
  docker compose -f "$REPO_DIR/compose.yaml" build

  log "starting MIAF"
  docker compose -f "$REPO_DIR/compose.yaml" up -d

  log "waiting for api container"
  wait_for_api_container 90 || fail "api container did not become ready for migrations"

  log "applying database migrations"
  docker compose -f "$REPO_DIR/compose.yaml" exec -T api python -m app.cli migrate

  log "waiting for HTTP health checks"
  wait_for_http "${APP_BASE_URL}/api/health" 90 || fail "${APP_BASE_URL}/api/health did not respond"
  wait_for_http "${APP_BASE_URL}/api/health/ready" 90 || fail "${APP_BASE_URL}/api/health/ready did not respond"

  log "running smoke checks"
  run_smoke
}

print_success() {
  cat <<EOF

MIAF is running locally.

Access URLs:
  - App: $APP_BASE_URL
  - API health: $APP_BASE_URL/api/health
  - API readiness: $APP_BASE_URL/api/health/ready
  - MinIO console: http://127.0.0.1:9001

Next steps:
  1. Open $APP_BASE_URL/onboarding
  2. Create the owner account
  3. Optionally configure Tailscale phone access
  4. Open /settings and choose your jurisdiction, currency, fiscal year, and AI provider
  5. Paste your AI provider key in /settings if you want OpenAI, Anthropic, or Gemini
  6. Upload a CSV or source file in /documents
  7. Use /agent for guided bookkeeping and analysis

CLI wrapper:
  - $BIN_DIR/miaf status
  - $BIN_DIR/miaf logs
  - $BIN_DIR/miaf update

Notes:
  - The installer never deletes volumes or user data.
  - Re-running this installer updates the repo, keeps your existing .env, rebuilds, re-runs migrations, and re-checks health.
  - If you want the miaf command on your PATH, add: export PATH="$BIN_DIR:\$PATH"
EOF
}

main() {
  detect_platform
  require_dependencies
  sync_repo
  bootstrap_env_file
  install_cli_wrapper
  start_stack
  print_success
}

main "$@"
