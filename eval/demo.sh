#!/usr/bin/env bash
# Replays a fintech-roast run over eval/fixture in a real terminal, at a readable pace.
# The findings, rule ids, and file:line are the actual output of the run scored in
# eval/RESULTS.md (recall 86%, 53 findings). This is the report shape the plugin prints;
# it is a canned replay for a GIF, not a live invocation.
#
# Record a GIF with:
#   asciinema rec -c 'bash eval/demo.sh' demo.cast
#   agg --font-size 26 --theme asciinema demo.cast demo.gif

set -u

# palette
DIM=$'\033[38;5;244m'; RST=$'\033[0m'; B=$'\033[1m'
CRIT=$'\033[38;5;203m'; HIGH=$'\033[38;5;179m'; RULE=$'\033[38;5;141m'
LOC=$'\033[38;5;244m'; EV=$'\033[38;5;250m'; GRN=$'\033[38;5;114m'
HL=$'\033[38;5;253m'; CYAN=$'\033[38;5;80m'

type() { printf '%s' "$1"; sleep "${2:-0.02}"; }
line() { printf '%b\n' "$1"; }
pause() { sleep "$1"; }

printf '%b' "${DIM}~/roastable-billing${RST} ${HL}\$${RST} "
for c in $(printf '%s' "/fintech-roast:roast" | sed -e 's/\(.\)/\1\n/g'); do
  printf '%s' "$c"; sleep 0.035
done
printf '\n\n'; pause 0.5

line "${DIM}scanning for money surfaces...${RST}"; pause 0.7
line "  found ${HL}11 files${RST}${DIM} across ${RST}${HL}10 domains${RST}${DIM}, one auditor each${RST}"; pause 0.5
line "  ${DIM}auditing, then verifying every finding...${RST}"; pause 0.9
printf '\n'

# sev  rule    loc                    tier       evidence
emit() { # $1 sev color, $2 SEV label, $3 rule, $4 loc, $5 tier, $6 evidence
  local tier=""
  [ "$5" = "likely" ] && tier=" ${DIM}likely${RST}"
  printf '%b\n' "$1${B}$(printf '%-9s' "$2")${RST}${RULE}$(printf '%-7s' "$3")${RST}${LOC}$4${RST}"
  printf '%b\n' "         ${EV}$6${RST}${tier}"
  sleep 0.28
}

line "${DIM}-- critical --${RST}"; pause 0.15
emit "$CRIT" CRITICAL "STO-1" "db/schema.sql:37"    confirmed "money columns typed DOUBLE PRECISION / REAL"
emit "$CRIT" CRITICAL "ROU-2" "src/split.ts:5"      confirmed "split rounds each share, the parts do not sum to the total"
emit "$CRIT" CRITICAL "IDE-1" "src/webhooks.ts:12"  confirmed "webhook credits the balance with no event-id dedup"
emit "$CRIT" CRITICAL "IDE-2" "src/webhooks.ts:19"  confirmed "charge is retried with no idempotency key"
emit "$CRIT" CRITICAL "IDE-3" "src/store.ts:18"     likely    "balance read-modify-write, lost updates under load"
emit "$CRIT" CRITICAL "LED-1" "src/ledger.ts:27"    confirmed "correctEntry mutates a posted ledger row in place"
emit "$CRIT" CRITICAL "LED-2" "db/schema.sql:33"    confirmed "single-entry movement, debits==credits unenforceable"
emit "$CRIT" CRITICAL "FX-4"  "src/fx.ts:39"        confirmed "totalRevenue sums amounts across currencies"
emit "$CRIT" CRITICAL "API-1" "src/api.ts:10"       confirmed "money serialized as a JSON number"
emit "$CRIT" CRITICAL "AGG-3" "src/reports.ts:11"   confirmed "paginated sum over live data double-counts"
line "${DIM}-- high --${RST}"; pause 0.15
emit "$HIGH" HIGH "TIM-2" "src/interest.ts:2"       confirmed "daysBetween divides epoch-ms by 86400000 (DST-naive)"
emit "$HIGH" HIGH "TAX-2" "src/tax.ts:20"           confirmed "tax back-calc, net + tax does not equal gross"
emit "$HIGH" HIGH "FX-1"  "src/fx.ts:16"            confirmed "refund assumes the reverse conversion is lossless"
emit "$HIGH" HIGH "API-3" "src/money.ts:2"          confirmed "parseFloat on a money input string"
line "${DIM}   ... 12 more high${RST}"; pause 0.3
line "${DIM}-- medium --${RST}"; pause 0.15
emit "$HIGH" MEDIUM "TST-2" "tests/billing.test.ts" confirmed "round-number fixtures hide every rounding bug"
line "${DIM}   ... 6 more medium${RST}"; pause 0.4

printf '\n'
line "${CRIT}${B}53 findings${RST}${DIM} across 10 domains  ${RST}${CRIT}20 critical${RST}  ${HIGH}26 high${RST}  ${DIM}7 medium${RST}"
pause 0.2
line "${DIM}each finding cites its rule. read ${RST}${CYAN}rules/${RST}${DIM} before you act.${RST}"
pause 2.2
