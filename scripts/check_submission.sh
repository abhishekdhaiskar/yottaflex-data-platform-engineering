#!/usr/bin/env bash
# Pre-submission self-check against the YottaFlex candidate guidelines.
# Usage: make check   (or: bash scripts/check_submission.sh)   Exit code 1 = something still to fix.
cd "$(dirname "$0")/.." || exit 1
fail=0
ok()  { echo "PASS  $1"; }
bad() { echo "FAIL  $1"; fail=1; }
warn(){ echo "WARN  $1"; }

echo "== 1. Required files (run it, show your work, AI use, reasoning)"
for f in README.md requirements.txt Makefile scripts/demo.sh config/pipeline.toml \
         prompts/PROMPT_LOG.md docs/AI_USAGE.md docs/design_note.md docs/data_dictionary.md docs/CODE_WALKTHROUGH.md \
         .github/workflows/ci.yml reports/test_results.txt reports/reconciliation.md reports/benchmark.txt; do
  [ -s "$f" ] && ok "$f" || bad "missing or empty: $f"
done

echo "== 2. Prompt history + AI disclosure are finished (no unfilled markers)"
if grep -rnE "TODO\(candidate\)|<paste|<e\.g\.|<YYYY|<tool" prompts docs README.md 2>/dev/null; then
  bad "unfinished placeholders above - replace each one with your real, truthful text"
else
  ok "no placeholders left in prompts/, docs/, README.md"
fi
n=$(grep -cE '^[0-9]+\. ' prompts/PROMPT_LOG.md 2>/dev/null || echo 0)
[ "$n" -ge 1 ] && ok "prompt log has $n numbered entries" || bad "prompt log has no numbered entries"

echo "== 3. No secrets / sensitive data in the public repo"
if grep -rIniE "(api[_-]?key|secret|passwd|password|token)[\"' ]*[:=][\"' ]*[A-Za-z0-9/+_-]{8,}|BEGIN [A-Z ]*PRIVATE KEY" \
     --exclude-dir=.git --exclude-dir=.venv --exclude=check_submission.sh . ; then
  bad "possible secret found above"
else
  ok "no secret-looking strings"
fi
[ -f .env ] && bad ".env exists (must not be committed)" || ok "no .env file"

echo "== 4. Environment"
python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null \
  && ok "Python >= 3.11" || bad "Python 3.11+ required (uses tomllib)"

echo "== 5. Git state (what reviewers will actually see)"
if [ -d .git ]; then
  mode=$(git ls-files -s scripts/demo.sh | cut -c1-6)
  [ "$mode" = "100755" ] && ok "scripts/demo.sh is executable in git" || bad "scripts/demo.sh not executable in git: git update-index --chmod=+x scripts/demo.sh"
  junk=$(git ls-files | grep -E "\.pyc$|__pycache__|\.egg-info|\.db$|\.env$|^logs/" || true)
  [ -z "$junk" ] && ok "no generated/junk files tracked" || { echo "$junk"; bad "junk tracked in git (list above)"; }
  git ls-files --error-unmatch reports/test_results.txt >/dev/null 2>&1 && ok "evidence reports are committed" || bad "reports/ not tracked: git add reports"
  git ls-files --error-unmatch .github/workflows/ci.yml >/dev/null 2>&1 && ok "CI workflow tracked" || bad "CI workflow not tracked"
  [ -z "$(git status --porcelain)" ] && ok "working tree clean (everything committed)" || warn "uncommitted changes: commit + push before submitting"
  c=$(git rev-list --count HEAD 2>/dev/null || echo 0)
  [ "$c" -ge 5 ] && ok "$c commits" || warn "only $c commits - make the evolution visible"
else
  warn "not a git repository here"
fi

echo
[ $fail -eq 0 ] && echo "ALL REQUIRED CHECKS PASSED" || echo "SOME CHECKS FAILED - fix the FAIL lines, then re-run: make check"
exit $fail
