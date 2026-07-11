#!/usr/bin/env sh
# Roast every commit's diff automatically, in the background.
#
# Install:  cp examples/post-commit-roast.sh .git/hooks/post-commit && chmod +x .git/hooks/post-commit
# Requires: the Claude Code CLI (`claude`) on PATH, with the fintech-roast plugin installed.
#
# How it works: the roast runs headless (`claude -p`) on the diff since the last roasted
# commit. The `fintech-roast.baseline` git config is the incremental marker: the skill
# diffs against it when set, and this hook advances it after each roast, so every commit
# is roasted exactly once. Delete the config key to fall back to diffing against the
# default branch.
#
# Cost note: each run spends your own Claude session usage (a diff-scoped roast is the
# cheap mode, but it is not free). The hook is opt-in per clone; nothing in the plugin
# installs it for you.

REPORT_DIR=$(git rev-parse --git-dir)/fintech-roast
mkdir -p "$REPORT_DIR"

(
  claude -p "/fintech-roast:roast diff" \
    > "$REPORT_DIR/report-$(git rev-parse --short HEAD).txt" 2>&1
  git config fintech-roast.baseline "$(git rev-parse HEAD)"
) >/dev/null 2>&1 &
