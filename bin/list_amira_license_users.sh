#!/bin/bash
# Print the users and machines currently holding AMIRA (AvizoSubMains) licenses,
# broken out by host group (MARS / VENUS), with start time and duration.
#
# Options:
#   -J   email j35@ornl.gov when MARS or VENUS pools are saturated, or when any
#        user is holding more than one license.
#   -t   email the full report to j35@ornl.gov (test mode).

MARS_TOTAL=4    # licenses reserved for cg1d-analysis* (MARS)
VENUS_TOTAL=3   # licenses reserved for bl10-analysis* (VENUS)
JEAN_EMAIL="j35@ornl.gov"

usage() {
    cat <<EOF
Usage: $(basename "$0") [-J] [-t] [-h]

Report users currently holding AMIRA (AvizoSubMains) licenses, split into
MARS (cg1d-analysis*) and VENUS (bl10-analysis*) host groups, with start
time and elapsed duration per session.

Options:
  -J          Send an alert email to ${JEAN_EMAIL} when any of:
                - all ${MARS_TOTAL} MARS (cg1d-analysis*) licenses are in use
                - all ${VENUS_TOTAL} VENUS (bl10-analysis*) licenses are in use
                - any user is holding more than one license
              No email is sent when none of the above is true.
  -t          Test mode: email the full report to ${JEAN_EMAIL}.
  -h, --help  Show this help message and exit.

Flags can be combined, e.g.  $(basename "$0") -Jt
EOF
}

# Support long "--help" alongside short "-h".
for arg in "$@"; do
    case "$arg" in
        -h|--help) usage; exit 0 ;;
    esac
done

notify_jean=0
test_mode=0
while getopts "Jth" opt; do
    case "$opt" in
        J) notify_jean=1 ;;
        t) test_mode=1   ;;
        h) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

# Extract: user \t machine \t "Day M/D HH:MM"
raw=$(license-status-amira | awk '
    /^Users of AvizoSubMains:/ { in_section = 1; next }
    /^Users of /               { in_section = 0 }
    in_section && $3 ~ /^\/dev\// {
        idx = index($0, "start ")
        if (idx > 0) {
            s = substr($0, idx + 6)
            printf "%s\t%s\t%s\n", $1, $2, s
        }
    }
')

now=$(date +%s)
current_year=$(date +%Y)

# Enrich each session with start_display, duration_display, duration_seconds, group
enriched=$(while IFS=$'\t' read -r user machine start_str; do
    [ -z "$user" ] && continue
    # start_str e.g. "Tue 4/21 13:47" — drop weekday
    md_hm=${start_str#* }
    start_epoch=$(date -d "$current_year/$md_hm" +%s 2>/dev/null)
    if [ -z "$start_epoch" ] || [ "$start_epoch" -gt "$now" ]; then
        start_epoch=$(date -d "$((current_year - 1))/$md_hm" +%s 2>/dev/null)
    fi
    if [ -z "$start_epoch" ]; then
        start_display="$start_str"
        dur_display="?"
        dur=0
    else
        start_display=$(date -d "@$start_epoch" "+%Y-%m-%d %H:%M")
        dur=$((now - start_epoch))
        days=$((dur / 86400))
        hours=$(( (dur % 86400) / 3600 ))
        mins=$(( (dur % 3600) / 60 ))
        dur_display=$(printf "%dd %02dh %02dm" "$days" "$hours" "$mins")
    fi

    case "$machine" in
        cg1d-analysis*) group="MARS"  ;;
        bl10-analysis*) group="VENUS" ;;
        *)              group="OTHER" ;;
    esac

    printf "%s\t%s\t%s\t%s\t%d\t%s\n" \
        "$user" "$machine" "$start_display" "$dur_display" "$dur" "$group"
done <<< "$raw")

BAR="========================================================================"

print_table() {
    local group="$1" total="$2" label="$3" pattern="$4"
    local rows count header
    rows=$(echo "$enriched" | awk -F'\t' -v g="$group" '$6 == g' \
           | sort -t$'\t' -k5,5nr)
    count=$(printf '%s' "$rows" | grep -c .)
    header=$(printf "%s  (%s)   ---   %d / %d licenses in use" \
             "$label" "$pattern" "$count" "$total")

    echo
    echo "$BAR"
    echo "  $header"
    echo "$BAR"
    printf '  %-20s %-28s %-18s %s\n' "USER" "MACHINE" "START" "DURATION"
    printf '  %-20s %-28s %-18s %s\n' "----" "-------" "-----" "--------"
    if [ -z "$rows" ]; then
        echo "  (none)"
    else
        echo "$rows" | awk -F'\t' '{ printf "  %-20s %-28s %-18s %s\n", $1, $2, $3, $4 }'
    fi
}

render_report() {
    print_table "MARS"  "$MARS_TOTAL"  "MARS"  "cg1d-analysis*"
    print_table "VENUS" "$VENUS_TOTAL" "VENUS" "bl10-analysis*"

    echo
    echo "$BAR"
    echo "  USERS HOLDING MORE THAN ONE LICENSE"
    echo "$BAR"
    local multi
    multi=$(echo "$enriched" \
        | awk -F'\t' '{ count[$1]++ } END { for (u in count) if (count[u] > 1) printf "  %-20s %d licenses\n", u, count[u] }' \
        | sort)
    if [ -z "$multi" ]; then
        echo "  (none)"
    else
        echo "$multi"
    fi

    echo
    echo "$BAR"
    echo "  INFO   ---   To release a user's license, run:  logoff_user <user>"
    echo "$BAR"
}

report=$(render_report)
echo "$report"

# Alert triggers for -J
mars_used=$(echo "$enriched"  | awk -F'\t' '$6 == "MARS"'  | grep -c .)
venus_used=$(echo "$enriched" | awk -F'\t' '$6 == "VENUS"' | grep -c .)
multi_users=$(echo "$enriched" \
    | awk -F'\t' '{ count[$1]++ } END { for (u in count) if (count[u] > 1) print u }' \
    | sort | tr '\n' ' ')
multi_users=${multi_users% }

triggers=()
[ "$mars_used"  -ge "$MARS_TOTAL"  ] && triggers+=("MARS saturated ($mars_used/$MARS_TOTAL)")
[ "$venus_used" -ge "$VENUS_TOTAL" ] && triggers+=("VENUS saturated ($venus_used/$VENUS_TOTAL)")
[ -n "$multi_users" ]               && triggers+=("multi-license users: $multi_users")

if [ "$notify_jean" -eq 1 ] && [ ${#triggers[@]} -gt 0 ]; then
    trigger_summary=$(IFS='; '; echo "${triggers[*]}")
    subject="[AMIRA] alert — ${trigger_summary}"
    {
        echo "AMIRA license alert triggered on $(hostname) at $(date '+%Y-%m-%d %H:%M')."
        echo
        for t in "${triggers[@]}"; do echo "  - $t"; done
        echo
        echo "$report"
    } | mail -s "$subject" "$JEAN_EMAIL"
    echo
    echo "Alert email sent to $JEAN_EMAIL (${#triggers[@]} trigger(s): ${trigger_summary})."
fi

if [ "$test_mode" -eq 1 ]; then
    subject="[AMIRA] test report — $(date '+%Y-%m-%d %H:%M')"
    echo "$report" | mail -s "$subject" "$JEAN_EMAIL"
    echo
    echo "Test report emailed to $JEAN_EMAIL."
fi
