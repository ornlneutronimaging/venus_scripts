#!/usr/bin/env bash
#
# list_and_fix_running_browser.sh - find (and optionally kill) the current
# user's Firefox / Jupyter processes across the shared analysis machines.
#
# Why this is needed
# ------------------
# The Firefox profile (~/.mozilla) lives on shared NFS/GPFS storage, so a
# Firefox running on ANY analysis node locks the profile. A new Firefox started
# on a different machine then refuses to launch ("Firefox is already running"),
# or leaves stale ".nfsXXXX" / "Device or resource busy" files behind.
#
# Jupyter is included because `jupyter-lab --browser=firefox` is what usually
# spawns those Firefox sessions; the Jupyter server is the live parent that
# holds files open and keeps the (often zombie) Firefox child around. Killing
# the Jupyter parent both frees the profile and reaps the zombie.
#
# It walks a fixed list of hosts over SSH (in parallel), so it needs
# passwordless SSH to those hosts (key in ~/.ssh/authorized_keys; on shared
# home dirs one key covers them all).
#
# Usage:
#   list_and_fix_running_browser.sh            # (default) list matching procs
#   list_and_fix_running_browser.sh list       # same as above
#   list_and_fix_running_browser.sh kill       # kill them, then verify
#   list_and_fix_running_browser.sh list -v    # also show clean/unreachable hosts
#   list_and_fix_running_browser.sh --help
#
set -uo pipefail

# ---------------------------------------------------------------------------
# Host list
# ---------------------------------------------------------------------------
HOSTS=(
    bl10-analysis1.sns.gov
    bl10-analysis2.sns.gov
    bl10-analysis6.sns.gov
    cg1d-analysis1.ornl.gov
    cg1d-analysis2.ornl.gov
)
# analysis.node01.sns.gov ... analysis.node30.sns.gov (some do not exist; they
# simply show up as "unreachable" and are skipped).
for n in $(seq -w 1 30); do
    HOSTS+=("analysis.node${n}.sns.gov")
done

SSH_OPTS=(
    -o BatchMode=yes
    -o ConnectTimeout=5
    -o StrictHostKeyChecking=accept-new
    -o LogLevel=ERROR
)

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
mode="list"
verbose=0
for arg in "$@"; do
    case "$arg" in
        list)        mode="list" ;;
        kill)        mode="kill" ;;
        -v|--verbose) verbose=1 ;;
        -h|--help)
            sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "$(basename "$0"): unknown argument '$arg' (try --help)" >&2
            exit 2
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Remote payload - runs on each host via `bash -s -- <mode>`.
#
# Single-quoted: every variable here is expanded REMOTELY, so $USER is the
# remote user (same account on shared home dirs).
#
# Process matching:
#   * Firefox/Chromium  -> by process NAME (pgrep -x), so we don't match
#     unrelated commands that merely mention a browser in their arguments.
#   * Jupyter           -> by full command line (pgrep -f). The "[l]" bracket
#     trick keeps this very command from matching itself.
#   * Zombies (<defunct>) are listed for information but never counted as
#     kill targets - they hold no files open and cannot be killed; they go
#     away when their parent (the Jupyter server) is killed.
# ---------------------------------------------------------------------------
read -r -d '' REMOTE_SCRIPT <<'REMOTE_EOF'
mode="${1:-list}"
me="$USER"

list_pids() {
    {
        pgrep -u "$me" -x 'firefox.*|chrome.*|chromium.*' 2>/dev/null
        pgrep -u "$me" -f 'jupyter-[l]ab|jupyter-[n]otebook' 2>/dev/null
    } | sed '/^$/d' | sort -un
}

# Subset of pids that are alive and not zombies -> the real kill targets.
live_pids() {
    local p st
    for p in $(list_pids); do
        st="$(ps -o stat= -p "$p" 2>/dev/null | tr -d ' ')"
        case "$st" in
            ""|Z*) ;;          # gone or zombie -> skip
            *) printf '%s\n' "$p" ;;
        esac
    done
}

pids="$(list_pids)"
if [ -z "$pids" ]; then
    echo "COUNT 0"
    exit 0
fi

count="$(printf '%s\n' "$pids" | wc -l | tr -d ' ')"
echo "COUNT $count"
# shellcheck disable=SC2086
ps -o pid=,stat=,args= -p $(printf '%s ' $pids) 2>/dev/null

if [ "$mode" = "kill" ]; then
    targets="$(live_pids | tr '\n' ' ')"
    if [ -n "${targets// /}" ]; then
        # shellcheck disable=SC2086
        kill $targets 2>/dev/null || true
        for _ in 1 2 3 4 5; do
            sleep 1
            [ -z "$(live_pids)" ] && break
        done
        leftover="$(live_pids | tr '\n' ' ')"
        if [ -n "${leftover// /}" ]; then
            # shellcheck disable=SC2086
            kill -9 $leftover 2>/dev/null || true
            sleep 1
        fi
    fi
    echo "REMAINING $(live_pids | grep -c .)"
fi
REMOTE_EOF

# ---------------------------------------------------------------------------
# Scan all hosts in parallel
# ---------------------------------------------------------------------------
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

scan_host() {
    local host="$1" out rc
    out="$(ssh "${SSH_OPTS[@]}" "$host" bash -s -- "$mode" <<<"$REMOTE_SCRIPT" 2>/dev/null)"
    rc=$?
    if [ "$rc" -ne 0 ] && [ -z "$out" ]; then
        printf 'UNREACHABLE\n' >"$tmp/$host"
    else
        printf '%s\n' "$out" >"$tmp/$host"
    fi
}

if [ "$mode" = "kill" ]; then
    echo "== Killing this user's Firefox / Jupyter processes on ${#HOSTS[@]} hosts =="
else
    echo "== Listing this user's Firefox / Jupyter processes on ${#HOSTS[@]} hosts =="
fi
echo

for h in "${HOSTS[@]}"; do
    scan_host "$h" &
done
wait

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
total_procs=0
hosts_with=0
unreachable=0
clean=0
remaining_total=0

for h in "${HOSTS[@]}"; do
    content="$(cat "$tmp/$h" 2>/dev/null)"

    if [ -z "$content" ] || [ "$content" = "UNREACHABLE" ]; then
        unreachable=$((unreachable + 1))
        [ "$verbose" -eq 1 ] && printf '  %-26s unreachable\n' "$h"
        continue
    fi

    count="$(printf '%s\n' "$content" | awk 'NR==1 && $1=="COUNT"{print $2}')"
    [ -z "$count" ] && count=0

    if [ "$count" -eq 0 ]; then
        clean=$((clean + 1))
        [ "$verbose" -eq 1 ] && printf '  %-26s clean\n' "$h"
        continue
    fi

    hosts_with=$((hosts_with + 1))
    total_procs=$((total_procs + count))

    printf '[%s] %s process(es):\n' "$h" "$count"
    # detail lines = everything except the COUNT / REMAINING markers
    printf '%s\n' "$content" | grep -vE '^(COUNT|REMAINING) ' | sed 's/^/    /'

    if [ "$mode" = "kill" ]; then
        rem="$(printf '%s\n' "$content" | awk '$1=="REMAINING"{print $2}')"
        [ -z "$rem" ] && rem=0
        remaining_total=$((remaining_total + rem))
        if [ "$rem" -eq 0 ]; then
            printf '    -> killed; none remaining\n'
        else
            printf '    -> WARNING: %s still running after kill\n' "$rem"
        fi
    fi
    echo
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "---------------------------------------------------------------"
if [ "$mode" = "kill" ]; then
    printf 'Found %s process(es) on %s host(s); %s still running after kill.\n' \
        "$total_procs" "$hosts_with" "$remaining_total"
else
    printf 'Found %s process(es) on %s host(s).\n' "$total_procs" "$hosts_with"
fi
printf '%s host(s) clean, %s unreachable (run with -v to list them).\n' \
    "$clean" "$unreachable"

if [ "$mode" = "list" ] && [ "$total_procs" -gt 0 ]; then
    echo
    echo "Re-run with 'kill' to terminate them:"
    echo "    $(basename "$0") kill"
fi
