#!/usr/bin/env bash
set -euo pipefail

if command -v py.exe >/dev/null 2>&1 && py.exe -3 -c "import sys" >/dev/null 2>&1; then
  python_cmd=(py.exe -3)
elif command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
  python_cmd=(python3)
elif command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
  python_cmd=(python)
else
  echo 'Python 3 is required for workflow contract tests.' >&2
  exit 127
fi


repo_root="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
skill_root="$repo_root/skill/astra"
svg_path="$repo_root/assets/astra-orchestrator.svg"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[[ -f "$skill_root/SKILL.md" ]] || fail 'SKILL.md is missing'
[[ -f "$skill_root/scripts/ask_astra.sh" ]] || fail 'ask_astra.sh is missing'
[[ -f "$skill_root/scripts/ask_astra.py" ]] || fail 'ask_astra.py is missing'
[[ -f "$skill_root/agents/openai.yaml" ]] || fail 'openai.yaml is missing'
[[ -x "$skill_root/scripts/ask_astra.sh" ]] || fail 'ask_astra.sh is not executable'

bash -n "$skill_root/scripts/ask_astra.sh"
bash -n "$repo_root/install.sh"
"${python_cmd[@]}" -B -m py_compile "$skill_root/scripts/ask_astra.py"

required_strings=(
  'GPT-6 Astra'
  'gpt-6-astra'
  'GPT-5.6 Luna'
  'GLM 5.3 Flash'
  'glm-5.3-flash'
  'BAI_API_KEY'
  'APIKEY_B_AI'
  'https://api.b.ai/v1'
  'B.AI Responses API'
)
for required in "${required_strings[@]}"; do
  rg -Fq "$required" "$skill_root/SKILL.md" "$skill_root/scripts/ask_astra.py" "$repo_root/README.md" || fail "missing required routing string: $required"
done

awk '
  /^interface:[[:space:]]*$/ { interface=1; next }
  /^[[:space:]]+display_name:[[:space:]]*"[^\"]+"[[:space:]]*$/ { display=1; next }
  /^[[:space:]]+short_description:[[:space:]]*"[^\"]+"[[:space:]]*$/ { short=1; next }
  /^[[:space:]]+default_prompt:[[:space:]]*"[^\"]+"[[:space:]]*$/ { prompt=1; next }
  END { exit !(interface && display && short && prompt) }
' "$skill_root/agents/openai.yaml" || fail 'openai.yaml failed basic YAML structure check'

if command -v xmllint >/dev/null 2>&1; then
  xmllint --noout "$svg_path" || fail 'SVG is not valid XML'
fi

rg -Fq 'viewBox="0 0 1200 600"' "$svg_path" || fail 'SVG viewBox is not 0 0 1200 600'
rg -Fq 'ASTRA' "$svg_path" || fail 'SVG is missing the Astra planning node'
rg -Fq 'GPT-5.6 LUNA' "$svg_path" || fail 'SVG is missing the Luna worker node'
rg -Fq 'GLM 5.3 FLASH' "$svg_path" || fail 'SVG is missing the GLM worker node'
if rg -n -i 'gradient|<filter([[:space:]>]|$)|<image([[:space:]>]|$)|url\(|@font-face|@import|fonts\.(googleapis|gstatic)|href=[^[:space:]]*(https?:|//)' "$svg_path"; then
  fail 'SVG contains a gradient, filter, external image, or external font reference'
fi

temp_root="$(mktemp -d /tmp/astra-orchestrator.XXXXXX)"
trap 'rm -rf "$temp_root"' EXIT
temp_home="$temp_root/home"
mkdir -p "$temp_home"

dry_run_output="$temp_root/dry-run.txt"
HOME="$temp_home" ASTRA_SKILLS_DIR= "$repo_root/install.sh" --dry-run >"$dry_run_output"
[[ ! -e "$temp_home/.codex" ]] || fail 'dry-run created a directory under HOME'
grep -Fq "$temp_home/.codex/skills/astra" "$dry_run_output" || fail 'dry-run omitted the default destination'

copy_home="$temp_root/copy-home"
HOME="$copy_home" "$repo_root/install.sh" --copy >/dev/null
for relative_path in SKILL.md scripts/ask_astra.sh scripts/ask_astra.py agents/openai.yaml; do
  cmp -s "$skill_root/$relative_path" "$copy_home/.codex/skills/astra/$relative_path" || fail "installed copy differs: $relative_path"
done
HOME="$copy_home" "$repo_root/install.sh" --copy >/dev/null

# Keep the scan practical: this test file contains the detection patterns, so exclude it.
if rg -n --hidden --glob '!.git/**' --glob '!tests/test_skill.sh' \
  -e '-----BEGIN [A-Z ]*PRIVATE KEY-----' \
  -e 'AKIA[0-9A-Z]{16}' \
  -e 'gh[pousr]_[A-Za-z0-9]{20,}' \
  -e 'sk-(ant-)?[A-Za-z0-9_-]{20,}' \
  -e 'xox[baprs]-[A-Za-z0-9-]{20,}' \
  "$repo_root"; then
  fail 'credential-shaped string found in repository'
fi

echo 'PASS: Astra orchestrator repository checks'

# LangChain workflow contract checks. These remain dependency-light.
[[ -f "$repo_root/pyproject.toml" ]] || fail 'pyproject.toml is missing'
[[ -f "$repo_root/workflow/engine.py" ]] || fail 'workflow engine is missing'
[[ -f "$repo_root/workflow/observability.py" ]] || fail 'workflow observability is missing'
[[ -f "$repo_root/workflow/HARNESS.md" ]] || fail 'workflow harness contract is missing'
"${python_cmd[@]}" -B -m py_compile "$repo_root/workflow/__init__.py" "$repo_root/workflow/agents.py" "$repo_root/workflow/cli.py" "$repo_root/workflow/config.py" "$repo_root/workflow/contracts.py" "$repo_root/workflow/engine.py" "$repo_root/workflow/observability.py" "$repo_root/workflow/tools.py"
"${python_cmd[@]}" -B -m unittest discover -s "$repo_root/tests" -p 'test_workflow.py'
