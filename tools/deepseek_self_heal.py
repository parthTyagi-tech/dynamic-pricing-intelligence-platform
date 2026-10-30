"""
DeepSeek Self-Healing Automation for CI/CD Pipeline.

When a CI/CD test failure occurs on a Pull Request, this script:
1. Gathers failure logs and stack traces from pytest/junit XML and build logs.
2. Implements a loop guard to prevent infinite healing cycles (max 2 attempts per PR).
3. Prompts DeepSeek to analyze the failure, pinpoint the buggy file, and generate a minimal fix.
4. Applies the fix to the source tree.
5. Verifies the fix locally in the runner.
6. If and ONLY if tests pass, commits and pushes to the PR branch and posts a summary comment.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_AUTO_HEAL_ATTEMPTS = 2
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def run_cmd(cmd: list[str] | str, check: bool = False, shell: bool = False) -> tuple[int, str]:
    """Execute a shell command and return exit code and combined output."""
    try:
        proc = subprocess.run(
            cmd,
            shell=shell,
            text=True,
            capture_output=True,
            check=check
        )
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return proc.returncode, output.strip()
    except Exception as e:
        return 1, str(e)


def check_loop_guard() -> bool:
    """Ensure we do not loop indefinitely by inspecting recent commit messages."""
    code, out = run_cmd(["git", "log", "-n", "5", "--pretty=format:%s"])
    if code != 0:
        print(f"[self-heal] Warning: Unable to inspect git log: {out}")
        return True

    auto_heal_count = 0
    for line in out.splitlines():
        if "[auto-heal]" in line or "fix(auto-heal)" in line:
            auto_heal_count += 1

    print(f"[self-heal] Consecutive auto-heal commits found: {auto_heal_count}/{MAX_AUTO_HEAL_ATTEMPTS}")
    if auto_heal_count >= MAX_AUTO_HEAL_ATTEMPTS:
        print("[self-heal] Max auto-healing attempts reached. Halting to prevent infinite loop. Human intervention required.")
        return False
    return True


def parse_junit_report(report_path: Path) -> dict:
    """Parse pytest junit XML report to locate failing test files and failure messages."""
    if not report_path.exists():
        return {}

    failures = []
    try:
        tree = ET.parse(report_path)
        root = tree.getroot()
        for testcase in root.iter("testcase"):
            for fail in testcase.findall("failure") + testcase.findall("error"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                file_attr = testcase.get("file", "")
                message = fail.get("message", "")
                body = (fail.text or "").strip()
                failures.append({
                    "test": f"{classname}::{name}",
                    "file": file_attr,
                    "message": message,
                    "traceback": body[-2000:] if len(body) > 2000 else body
                })
    except Exception as e:
        print(f"[self-heal] Warning parsing JUnit XML: {e}")

    return {"failures": failures}


def extract_failing_context() -> tuple[str, list[str]]:
    """Collect failure context and candidate source file paths to provide to DeepSeek."""
    context_lines = []
    candidate_files = set()

    # 1. Parse JUnit report
    junit_path = Path("backend/reports/junit.xml")
    junit_data = parse_junit_report(junit_path)
    if junit_data.get("failures"):
        context_lines.append("### Pytest Failure Details:")
        for idx, f in enumerate(junit_data["failures"][:3], 1):
            context_lines.append(f"\nFailure #{idx}: {f['test']}")
            context_lines.append(f"Message: {f['message']}")
            context_lines.append(f"Traceback:\n{f['traceback']}")
            if f.get("file"):
                candidate_files.add(f["file"])

    # 2. Check for manual failure log artifact if passed
    log_file = Path("ci_failure.log")
    if log_file.exists():
        raw_log = log_file.read_text(encoding="utf-8", errors="ignore")
        # Extract referenced python/typescript files
        for match in re.findall(r'([a-zA-Z0-9_\-\./\\]+\.(?:py|tsx|ts|js|jsx))', raw_log):
            clean_path = match.replace("\\", "/")
            if Path(clean_path).exists() and not clean_path.startswith(".git"):
                candidate_files.add(clean_path)
        context_lines.append("\n### Raw CI Step Error Log (tail 100 lines):")
        tail = "\n".join(raw_log.splitlines()[-100:])
        context_lines.append(tail)

    return "\n".join(context_lines), sorted(candidate_files)


def call_deepseek(api_key: str, prompt: str) -> str:
    """Send diagnostic prompt to DeepSeek API."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are DeepSeek Harness Self-Healing Agent. You analyze software CI/CD failures and output "
                    "precise, minimal bug fixes. Always preserve existing intended behavior. "
                    "Return strictly valid JSON with no markdown wrapping or conversational prose."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4096
    }

    req = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]


def post_github_comment(pr_number: str, message: str, token: str, repo: str) -> None:
    """Post an auto-heal audit comment back to the GitHub PR."""
    if not (pr_number and token and repo):
        return
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    req = urllib.request.Request(
        url,
        data=json.dumps({"body": message}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DeepSeek-AutoHeal"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15):
            print(f"[self-heal] Posted diagnostic comment to PR #{pr_number}")
    except Exception as e:
        print(f"[self-heal] Notice: Could not post comment to PR #{pr_number}: {e}")


def main() -> int:
    print("=== [DeepSeek Harness] CI/CD Self-Healing Agent Starting ===")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("[self-heal] Error: DEEPSEEK_API_KEY environment variable is missing. Skipping auto-heal.")
        return 0

    head_ref = os.environ.get("GITHUB_HEAD_REF")
    if not head_ref:
        print("[self-heal] Not a pull_request event (GITHUB_HEAD_REF unset). Skipping.")
        return 0

    if not check_loop_guard():
        return 0

    failure_context, candidate_files = extract_failing_context()
    if not failure_context:
        print("[self-heal] No failure context found to diagnose. Skipping.")
        return 0

    print(f"[self-heal] Identified {len(candidate_files)} relevant candidate file(s): {candidate_files}")

    # Gather file contents for candidate files (up to 3 files to fit token window)
    file_snippets = []
    for fpath in candidate_files[:3]:
        p = Path(fpath)
        if p.exists() and p.is_file():
            content = p.read_text(encoding="utf-8", errors="ignore")
            # Limit snippet size
            lines = content.splitlines()
            snippet = "\n".join(lines[:300])
            file_snippets.append(f"--- FILE: {fpath} ---\n{snippet}")

    prompt = f"""A CI test failed on branch '{head_ref}'.
Failure Diagnostics:
{failure_context}

Source Code Context:
{chr(10).join(file_snippets)}

Analyze the root cause. If the bug is in the source code or test configuration, provide the fix.
You MUST output ONLY a valid JSON object matching this schema:
{{
  "file_path": "path/to/file_to_modify",
  "search_block": "exact unique block of lines in existing file to replace",
  "replace_block": "the replacement code block that fixes the bug",
  "explanation": "concise description of what caused the bug and how this fix resolves it"
}}
Do NOT include markdown code blocks around the JSON. Return raw JSON only.
"""

    print("[self-heal] Querying DeepSeek for automated repair proposal...")
    try:
        response_text = call_deepseek(api_key, prompt).strip()
        # Clean potential markdown wrapping
        if response_text.startswith("```"):
            response_text = re.sub(r"^```[a-z]*\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)
        patch_data = json.loads(response_text)
    except Exception as e:
        print(f"[self-heal] Failed to parse DeepSeek response: {e}")
        return 0

    target_file = Path(patch_data.get("file_path", ""))
    search_block = patch_data.get("search_block", "")
    replace_block = patch_data.get("replace_block", "")
    explanation = patch_data.get("explanation", "Automated fix applied.")

    if not (target_file.exists() and search_block and replace_block):
        print(f"[self-heal] Invalid patch data received: target={target_file}, has_search={bool(search_block)}")
        return 0

    original_content = target_file.read_text(encoding="utf-8")
    if search_block not in original_content:
        print(f"[self-heal] search_block not found in {target_file}. Aborting patch to protect code integrity.")
        return 0

    print(f"[self-heal] Applying proposed patch to {target_file}...")
    patched_content = original_content.replace(search_block, replace_block, 1)
    target_file.write_text(patched_content, encoding="utf-8")

    # Local Verification Gate
    print("[self-heal] Verifying fix locally before committing...")
    test_code, _test_out = run_cmd(["pytest", "-m", "not live and not network", "-q"], shell=True)
    if test_code != 0:
        print(f"[self-heal] Local tests failed after patch (exit code {test_code}). Reverting changes.")
        target_file.write_text(original_content, encoding="utf-8")
        return 0

    print("[self-heal] All tests passed locally! Staging, committing, and pushing auto-heal fix...")
    run_cmd(["git", "config", "user.name", "github-actions[bot]"])
    run_cmd(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])
    run_cmd(["git", "add", str(target_file)])
    commit_msg = f"fix(auto-heal): {explanation} [auto-heal]"
    run_cmd(["git", "commit", "-m", commit_msg])

    push_code, push_out = run_cmd(["git", "push", "origin", f"HEAD:{head_ref}"])
    if push_code == 0:
        print(f"[self-heal] Successfully pushed auto-heal fix to branch '{head_ref}'.")
        pr_number = os.environ.get("PR_NUMBER", "")
        gh_token = os.environ.get("GITHUB_TOKEN", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        post_github_comment(
            pr_number,
            f"### 🤖 DeepSeek Harness Self-Healing\n\nA test failure occurred in CI. DeepSeek diagnosed and applied the following fix:\n\n> {explanation}\n\n- **Modified File**: `{target_file}`\n- **Commit**: `{commit_msg}`\n- **Verification**: Local pytest suite confirmed 100% passing before push.",
            gh_token,
            repo
        )
    else:
        print(f"[self-heal] Warning: Git push failed: {push_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
