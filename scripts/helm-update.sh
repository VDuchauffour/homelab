#!/usr/bin/env bash
# helm-update.sh — Helm release updater with per-app hooks
#
# Updates helmfile-managed releases with optional scale-down/scale-up
# hooks for apps that need graceful restarts (e.g., GPU-bound workloads).
#
# Usage:
#   helm-update.sh <app>                 Update a single app
#   helm-update.sh --all                 Update all apps
#   helm-update.sh --diff <app>          Show diff only
#   helm-update.sh --diff --all          Diff all apps
#   helm-update.sh --json <app>          JSON output (for n8n)
#   helm-update.sh --infra <service>     Update an infra service
#
# n8n integration:
#   Call with --json to get structured output on stdout.
#   All progress/helmfile output goes to stderr.
#   stdout contains only the final JSON summary.
#
# Exit codes:
#   0  Success (applied, or no changes in --diff mode)
#   1  Error (at least one app failed)
#   2  Changes detected (--diff mode, single app only)
#
# Environment:
#   HELM_UPDATE_HOOKS_FILE  Path to hooks config (default: scripts/helm-update-hooks.conf)
#   HELM_UPDATE_TIMEOUT     Scale/rollout timeout in seconds (default: 120)
#   HELM_UPDATE_SETTLE      Seconds to wait after scale-down for device release (default: 5)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_FILE="${HELM_UPDATE_HOOKS_FILE:-$SCRIPT_DIR/helm-update-hooks.conf}"
APPS_DIR="$ROOT_DIR/kubernetes/apps"
INFRA_DIR="$ROOT_DIR/kubernetes/infra"
TIMEOUT="${HELM_UPDATE_TIMEOUT:-120}"
SETTLE="${HELM_UPDATE_SETTLE:-5}"

# -- State --
MODE="apply"
FORMAT="text"
SCOPE="apps"
TARGET=""
HAS_ERRORS=false
RESULTS_FILE=""
CURRENT_APP=""
CURRENT_HOOK_ENTRIES=""

# -- Helpers --

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }
die() {
	log "ERROR: $*"
	exit 1
}

usage() {
	cat >&2 <<'EOF'
Usage: helm-update.sh [OPTIONS] <app|--all>

Options:
  --diff           Show diff only, don't apply
  --json           Output JSON to stdout (for n8n)
  --infra          Target kubernetes/infra/ instead of kubernetes/apps/
  --timeout SEC    Scale/rollout timeout in seconds (default: 120)
  --settle SEC     Wait time after scale-down for device release (default: 5)
  --help, -h       Show this help

Examples:
  helm-update.sh jellyfin              Update Jellyfin (with scale-down hook)
  helm-update.sh --diff sonarr         Check if Sonarr has pending changes
  helm-update.sh --all --json          Update all apps, JSON output for n8n
  helm-update.sh --infra traefik       Update Traefik ingress
  helm-update.sh --diff --all          Diff all apps

Hook config:
  Per-app hooks are defined in scripts/helm-update-hooks.conf.
  Apps listed there will be scaled to 0 before helmfile apply
  and back to 1 after, with an EXIT trap for safety.
EOF
}

append_result() {
	local app="$1" status="$2" message="$3" duration="$4"
	printf '{"app":"%s","status":"%s","message":"%s","duration":%d}\n' \
		"$app" "$status" "$message" "$duration" >>"$RESULTS_FILE"
}

emit_json() {
	[[ "$FORMAT" != "json" ]] && return
	local total=0 success=0 no_changes=0 errors=0 warnings=0 changes=0
	local items=""

	while IFS= read -r line; do
		[[ -z "$line" ]] && continue
		items="${items:+$items,}$line"
		total=$((total + 1))
		case "$line" in
		*'"success"'*) success=$((success + 1)) ;;
		*'"no_changes"'*) no_changes=$((no_changes + 1)) ;;
		*'"error"'*) errors=$((errors + 1)) ;;
		*'"warning"'*) warnings=$((warnings + 1)) ;;
		*'"changes_detected"'*) changes=$((changes + 1)) ;;
		esac
	done <"$RESULTS_FILE"

	printf '{"results":[%s],"summary":{"total":%d,"success":%d,"no_changes":%d,"changes_detected":%d,"errors":%d,"warnings":%d}}\n' \
		"$items" "$total" "$success" "$no_changes" "$changes" "$errors" "$warnings"
}

# -- Preflight --

preflight() {
	for cmd in helmfile kubectl; do
		command -v "$cmd" >/dev/null || die "$cmd is not installed or not in PATH"
	done
}

# -- Hook Management --

declare -A HOOK_TARGETS=()

load_hooks() {
	[[ ! -f "$HOOKS_FILE" ]] && return
	while IFS= read -r line; do
		[[ "$line" =~ ^[[:space:]]*# ]] && continue
		[[ -z "${line// /}" ]] && continue
		IFS=: read -r app ns type name <<<"$line"
		[[ -z "$app" || -z "$ns" || -z "$type" || -z "$name" ]] && continue
		HOOK_TARGETS["$app"]+="${ns}:${type}:${name} "
	done <"$HOOKS_FILE"
}

# -- Cleanup trap --
# Guarantees scale-back-up even on crash or SIGINT/SIGTERM.

cleanup() {
	if [[ -n "$CURRENT_HOOK_ENTRIES" ]]; then
		log "$CURRENT_APP: scaling back up (cleanup trap)..."
		for entry in $CURRENT_HOOK_ENTRIES; do
			IFS=: read -r ns type name <<<"$entry"
			kubectl scale "$type/$name" -n "$ns" --replicas=1 --timeout="${TIMEOUT}s" 2>/dev/null || true
		done
		CURRENT_HOOK_ENTRIES=""
	fi
	[[ -n "$RESULTS_FILE" ]] && rm -f "$RESULTS_FILE"
}

trap cleanup EXIT INT TERM

# -- Scale helpers --

wait_scale_down() {
	local ns="$1" type="$2" name="$3"
	local deadline=$((SECONDS + TIMEOUT))
	while ((SECONDS < deadline)); do
		local replicas
		replicas=$(kubectl get "$type/$name" -n "$ns" \
			-o jsonpath='{.status.replicas}' 2>/dev/null || echo "0")
		[[ "${replicas:-0}" == "0" || -z "$replicas" ]] && return 0
		sleep 3
	done
	return 1
}

wait_rollout() {
	local ns="$1" type="$2" name="$3"
	kubectl rollout status "$type/$name" -n "$ns" --timeout="${TIMEOUT}s" >/dev/null 2>&1
}

# -- Core Logic --

resolve_app_dir() {
	local app="$1"
	if [[ "$SCOPE" == "infra" ]]; then
		echo "$INFRA_DIR/$app"
	else
		echo "$APPS_DIR/$app"
	fi
}

update_app() {
	local app="$1"
	local app_dir
	app_dir=$(resolve_app_dir "$app")
	local start_time=$SECONDS

	# Validate
	if [[ ! -d "$app_dir" ]]; then
		log "$app: directory not found ($app_dir)"
		append_result "$app" "error" "Directory not found" "0"
		HAS_ERRORS=true
		return 0 # don't abort --all
	fi

	if [[ ! -f "$app_dir/helmfile.yaml" ]]; then
		log "$app: no helmfile.yaml found, skipping"
		append_result "$app" "error" "No helmfile.yaml" "0"
		HAS_ERRORS=true
		return 0
	fi

	# Check for hooks
	local has_hooks=false
	local hook_entries=""
	if [[ -n "${HOOK_TARGETS[$app]+x}" ]]; then
		has_hooks=true
		hook_entries="${HOOK_TARGETS[$app]}"
	fi

	# ---- Diff mode ----
	if [[ "$MODE" == "diff" ]]; then
		log "$app: checking for changes..."
		local diff_exit=0
		helmfile -f "$app_dir/helmfile.yaml" diff --suppress-secrets >&2 2>&1 || diff_exit=$?

		local duration=$((SECONDS - start_time))
		case $diff_exit in
		0)
			log "$app: up to date"
			append_result "$app" "no_changes" "Up to date" "$duration"
			return 0
			;;
		2)
			log "$app: has pending changes"
			append_result "$app" "changes_detected" "Has pending changes" "$duration"
			return 0
			;;
		*)
			log "$app: diff failed (exit $diff_exit)"
			append_result "$app" "error" "Diff failed" "$duration"
			HAS_ERRORS=true
			return 0
			;;
		esac
	fi

	# ---- Apply mode ----

	# Pre-update: scale down
	if $has_hooks; then
		CURRENT_APP="$app"
		CURRENT_HOOK_ENTRIES="$hook_entries"

		for entry in $hook_entries; do
			IFS=: read -r ns type name <<<"$entry"
			log "$app: scaling down $type/$name in $ns..."
			if ! kubectl scale "$type/$name" -n "$ns" --replicas=0 --timeout="${TIMEOUT}s" >&2; then
				log "$app: failed to scale down $type/$name"
				append_result "$app" "error" "Scale down failed for $type/$name" "$((SECONDS - start_time))"
				HAS_ERRORS=true
				return 0 # trap will scale back up
			fi
		done

		for entry in $hook_entries; do
			IFS=: read -r ns type name <<<"$entry"
			log "$app: waiting for $type/$name to terminate..."
			if ! wait_scale_down "$ns" "$type" "$name"; then
				log "$app: WARNING: $type/$name did not terminate within ${TIMEOUT}s"
			fi
		done

		log "$app: waiting ${SETTLE}s for device release..."
		sleep "$SETTLE"
	fi

	# Apply
	log "$app: running helmfile apply..."
	if ! helmfile -f "$app_dir/helmfile.yaml" apply --suppress-secrets >&2; then
		log "$app: helmfile apply FAILED"
		append_result "$app" "error" "helmfile apply failed" "$((SECONDS - start_time))"
		HAS_ERRORS=true
		return 0 # trap will scale back up if hooks were set
	fi

	# Post-update: scale back up
	if $has_hooks; then
		for entry in $hook_entries; do
			IFS=: read -r ns type name <<<"$entry"
			log "$app: scaling up $type/$name..."
			kubectl scale "$type/$name" -n "$ns" --replicas=1 --timeout="${TIMEOUT}s" >&2 || true
		done

		for entry in $hook_entries; do
			IFS=: read -r ns type name <<<"$entry"
			log "$app: waiting for $type/$name to be ready..."
			if ! wait_rollout "$ns" "$type" "$name"; then
				log "$app: WARNING: $type/$name not ready within ${TIMEOUT}s"
				append_result "$app" "warning" "Applied but $type/$name not ready" "$((SECONDS - start_time))"
				CURRENT_HOOK_ENTRIES=""
				return 0
			fi
		done

		# Successful — clear hook state so trap is a no-op
		CURRENT_HOOK_ENTRIES=""
	fi

	local duration=$((SECONDS - start_time))
	log "$app: done (${duration}s)"
	append_result "$app" "success" "Updated successfully" "$duration"
	return 0
}

# -- Main --

while [[ $# -gt 0 ]]; do
	case $1 in
	--diff)
		MODE="diff"
		shift
		;;
	--json)
		FORMAT="json"
		shift
		;;
	--infra)
		SCOPE="infra"
		shift
		;;
	--all)
		TARGET="__all__"
		shift
		;;
	--timeout)
		TIMEOUT="$2"
		shift 2
		;;
	--settle)
		SETTLE="$2"
		shift 2
		;;
	--help | -h)
		usage
		exit 0
		;;
	-*) die "Unknown option: $1" ;;
	*)
		TARGET="$1"
		shift
		;;
	esac
done

[[ -z "$TARGET" ]] && {
	usage
	exit 1
}

preflight
load_hooks
RESULTS_FILE=$(mktemp)

if [[ "$TARGET" == "__all__" ]]; then
	[[ "$SCOPE" == "infra" ]] && die "--all is not supported with --infra (too risky). Specify services individually."

	app_list=()
	for dir in "$APPS_DIR"/*/; do
		[[ -f "$dir/helmfile.yaml" ]] && app_list+=("$(basename "$dir")")
	done

	log "Processing ${#app_list[@]} apps..."
	for app in $(printf '%s\n' "${app_list[@]}" | sort); do
		update_app "$app"
	done
else
	update_app "$TARGET"
fi

# Emit JSON summary to stdout
emit_json

# Exit with error if any app failed
if $HAS_ERRORS; then
	exit 1
fi
exit 0
