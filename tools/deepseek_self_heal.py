"""
DeepSeek & Groq Autonomous Self-Healing Automation for CI/CD Pipeline (Hardened Engine).

Phase 1 Hardened Architecture:
- Strict path resolution and traversal jailbreak prevention (symlink recursion, anchored allowlist).
- Scrubbed child process environments (no leaked credentials, process-tree termination on timeout).
- Exact xunit1 pytest node ID targeting (file::Class::test[param]) without -k fallback.
- Pre-LLM failure classification: FLAKY probe, NON_CODE / infra filter, COLLECTION_ERROR detection.
- Selective secret redaction (API keys, tokens, auth headers; preserves port/localhost).
- Byte-level CRLF-safe patching with exact-once search block matching and assertion safety checks.
- Protocol-based LLM provider architecture with multi-key failover and Retry-After backoff.
- Multi-attempt retry loop (max 3) with verification failure feedback.
- Telemetry logging to reports/heal_metrics.json in a finally block.
"""

from __future__ import annotations

import os
import sys
import json
import re
import time
import subprocess
import signal
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Protocol, runtime_checkable, Any


# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------
MAX_AUTO_HEAL_ATTEMPTS = 2
MAX_ENGINE_ATTEMPTS = 3
MAX_CONTEXT_CHARS = 16000
MAX_PATCH_LINES = 60
MAX_PATCH_FILES = 3
MAX_LLM_CALL_BUDGET = 4

STAGE1_TIMEOUT_SECONDS = 30.0
STAGE2_TIMEOUT_SECONDS = 180.0

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "qwen/qwen3.8-27b"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

ALLOWLIST_PREFIX = "backend/app/"
ANCHORED_DENY_PREFIXES = (".github/", "tools/", "docs/", "frontend/", ".env")
FORBIDDEN_FILE_PATTERNS = (r"conftest\.py$", r"test_.*\.py$", r".*_test\.py$")
FORBIDDEN_PATCH_PATTERNS = (
    r"@pytest\.mark\.skip",
    r"@pytest\.mark\.xfail",
    r"pytest\.skip\(",
    r"pytest\.xfail\(",
    r"subprocess\.",
    r"os\.system\(",
    r"os\.popen\(",
    r"\beval\(",
    r"\bexec\(",
    r"socket\.",
    r"requests\.",
    r"urllib\.request"
)

SECRET_KEY_NAME_REGEX = re.compile(r"(?i)(KEY|TOKEN|SECRET|PASSWORD|AUTH)")
SECRET_PATTERNS = [
    re.compile(r"gsk_[a-zA-Z0-9]{20,}"),
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{10,}"),
    re.compile(r"(?i)Authorization:\s*[^\r\n]+")
]


# ---------------------------------------------------------------------------
# Provider Protocol & Concrete Implementations
# ---------------------------------------------------------------------------
@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def generate_patch(self, prompt: str) -> tuple[str, dict[str, Any]]:
        """Returns (raw_response_text, telemetry_dict)."""
        ...


class BaseHTTPProvider:
    def __init__(self, name: str, api_url: str, model_name: str, api_key: str):
        self.name = name
        self.api_url = api_url
        self.model_name = model_name
        self.api_key = api_key

    def generate_patch(self, prompt: str) -> tuple[str, dict[str, Any]]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "DeepSeek-SelfHeal-Bot"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert Autonomous CI/CD Self-Healing Agent. You analyze software test failures "
                        "and output precise, minimal bug fixes. Always preserve existing intended behavior. "
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
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            return content, {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            }


class FailoverProvider:
    """Manages ordered failover across Groq and DeepSeek keys with Retry-After and budget tracking."""

    def __init__(self, providers: list[BaseHTTPProvider], sleep_fn: Any = time.sleep, max_budget: int = MAX_LLM_CALL_BUDGET):
        self.providers = list(providers)
        self.sleep_fn = sleep_fn
        self.max_budget = max_budget
        self.total_calls = 0
        self.disabled_providers: set[str] = set()
        self.name = "FailoverProvider"

    def generate_patch(self, prompt: str) -> tuple[str, dict[str, Any]]:
        if self.total_calls >= self.max_budget:
            raise RuntimeError(f"Exceeded maximum LLM call budget of {self.max_budget} calls.")

        last_error = "No active providers available."
        for provider in list(self.providers):
            if provider.name in self.disabled_providers:
                continue

            self.total_calls += 1
            masked_key = provider.api_key[:7] + "..." + provider.api_key[-4:] if len(provider.api_key) > 12 else "***"
            print(f"[self-heal] Attempting repair via {provider.name} ({masked_key}) with model '{provider.model_name}'...")

            try:
                content, usage = provider.generate_patch(prompt)
                usage["provider_used"] = provider.name
                self.name = provider.name
                return content, usage
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="ignore")
                print(f"[self-heal] HTTP Error {e.code} on {provider.name}: {error_body}")

                # Context-length 400: Do NOT failover (problem is prompt size, not key)
                if e.code == 400 and ("context_length" in error_body.lower() or "too many tokens" in error_body.lower()):
                    raise RuntimeError(f"Context length exceeded on {provider.name}: {error_body}")

                # 401 / 403: Disable key for remainder of run
                if e.code in (401, 403):
                    print(f"[self-heal] Key disabled due to auth error {e.code} on {provider.name}.")
                    self.disabled_providers.add(provider.name)
                    last_error = f"{provider.name}: HTTP {e.code}"
                    continue

                # 429 / 5xx / Rate limit: Failover with Retry-After
                if e.code in (429, 500, 502, 503, 504) or "rate_limit" in error_body.lower() or "quota" in error_body.lower():
                    retry_after_hdr = e.headers.get("Retry-After") if hasattr(e, "headers") else None
                    sleep_sec = float(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else 1.0
                    print(f"[self-heal] Quota/Rate limit on {provider.name}. Backing off {sleep_sec}s then failing over...")
                    self.sleep_fn(min(sleep_sec, 5.0))
                    last_error = f"{provider.name}: HTTP {e.code}"
                    continue

                raise
            except (urllib.error.URLError, TimeoutError) as e:
                print(f"[self-heal] Timeout/Connection error on {provider.name}: {e}. Failing over...")
                last_error = f"{provider.name}: {e}"
                continue

        raise RuntimeError(f"All configured LLM providers failed or exhausted. Last error: {last_error}")


def build_default_provider() -> LLMProvider:
    """Build the production failover provider pool from environment secrets."""
    providers: list[BaseHTTPProvider] = []

    raw_groq_keys = os.environ.get("GROQ_API_KEYS", "")
    key1 = os.environ.get("GROQ_API_KEY", "")
    key2 = os.environ.get("GROQ_API_KEY_BACKUP", "")

    collected_groq = []
    if raw_groq_keys:
        collected_groq.extend([k.strip() for k in raw_groq_keys.split(",") if k.strip()])
    if key1 and key1 not in collected_groq:
        collected_groq.append(key1)
    if key2 and key2 not in collected_groq:
        collected_groq.append(key2)

    for idx, gkey in enumerate(collected_groq, 1):
        providers.append(BaseHTTPProvider(f"Groq Key #{idx}", GROQ_API_URL, GROQ_MODEL, gkey))

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        providers.append(BaseHTTPProvider("DeepSeek API", DEEPSEEK_API_URL, DEEPSEEK_MODEL, deepseek_key))

    if not providers:
        raise RuntimeError("No Groq or DeepSeek API keys configured in environment.")

    return FailoverProvider(providers)


# ---------------------------------------------------------------------------
# Path & Jailbreak Security
# ---------------------------------------------------------------------------
def get_repo_root() -> Path:
    """Return the absolute path of the repository root."""
    return Path(__file__).resolve().parent.parent


def resolve_workspace_path(raw_path: str | Path, repo_root: Path | None = None) -> Path | None:
    """
    Resolve workspace path across root, backend/, or frontend/.
    Enforces jailbreak checks: escapes outside repo root and parent directory symlinks are rejected.
    Returns resolved Path object or None if invalid/forbidden.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    repo_root = repo_root.resolve()
    raw_str = str(raw_path).replace("\\", "/").strip()
    if not raw_str:
        return None

    # Explicitly reject absolute paths
    if os.path.isabs(str(raw_path)) or (len(raw_str) > 1 and raw_str[1] == ":") or raw_str.startswith("/"):
        return None

    # Check candidates
    candidates = [
        repo_root / raw_str,
        repo_root / "backend" / raw_str,
        repo_root / "frontend" / raw_str
    ]
    if raw_str.startswith("backend/"):
        candidates.append(repo_root / raw_str[8:])
    elif raw_str.startswith("frontend/"):
        candidates.append(repo_root / raw_str[9:])

    for cand in candidates:
        try:
            resolved = cand.resolve()
        except (ValueError, RuntimeError):
            continue

        if not resolved.exists() or not resolved.is_file():
            continue

        # Check 1: Inside repo root
        try:
            resolved.relative_to(repo_root)
        except ValueError:
            return None

        # Check 2: Check every component up to repo_root for symlinks
        curr = resolved
        has_symlink = False
        while curr != repo_root and curr != curr.parent:
            if curr.is_symlink():
                has_symlink = True
                break
            curr = curr.parent

        if has_symlink:
            return None

        return resolved

    return None


def get_backend_cwd(repo_root: Path | None = None) -> Path:
    """Return working directory where backend pytest.ini resides."""
    if repo_root is None:
        repo_root = get_repo_root()
    backend_dir = repo_root / "backend"
    if (backend_dir / "pytest.ini").exists():
        return backend_dir
    return repo_root


# ---------------------------------------------------------------------------
# Process Execution Guard (Scrubbed Env & Timeout Management)
# ---------------------------------------------------------------------------
def get_scrubbed_env() -> dict[str, str]:
    """
    Build a sanitized subprocess environment.
    Inherits only essential system and testing variables; strips all tokens and secrets.
    """
    safe_keys = {
        "PATH", "PYTHONPATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE",
        "VIRTUAL_ENV", "PYTEST_ADDOPTS"
    }
    scrubbed = {k: v for k, v in os.environ.items() if k in safe_keys}
    scrubbed.update({
        "FLASK_ENV": "testing",
        "MOCK_SCRAPING": "true",
        "DATABASE_URL": "sqlite:///:memory:",
        "SECRET_KEY": "ci-testing-secret-key-32-chars-minimum-safe!!",
        "JWT_SECRET_KEY": "ci-testing-jwt-secret-key-32-chars-safe!!"
    })
    return scrubbed


def kill_process_tree(pid: int) -> None:
    """Safely terminate a process and all its children across Windows and POSIX."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
        else:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        pass


def run_cmd(
    cmd: list[str],
    cwd: str | Path | None = None,
    timeout: float = 30.0,
    env: dict[str, str] | None = None
) -> tuple[int, str]:
    """
    Execute command as an argument list with scrubbed environment and process-tree timeout.
    Returns (exit_code, combined_output).
    """
    proc_env = env if env is not None else get_scrubbed_env()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=proc_env
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            out = (stdout or "") + ("\n" + stderr if stderr else "")
            return proc.returncode, out.strip()
        except subprocess.TimeoutExpired:
            kill_process_tree(proc.pid)
            try:
                proc.kill()
            except Exception:
                pass
            return 124, f"Command timed out after {timeout} seconds and was terminated."
    except Exception as e:
        return 1, str(e)


# ---------------------------------------------------------------------------
# Loop Guard
# ---------------------------------------------------------------------------
def check_loop_guard(base_ref: str | None = None, repo_root: Path | None = None) -> bool:
    """
    Inspect git history across PR range (origin/{base_ref}..HEAD or {base_ref}..HEAD)
    to ensure consecutive auto-heal commits do not exceed limit (MAX_AUTO_HEAL_ATTEMPTS = 2).
    Enforces anti-spoofing: only commits authored by 'github-actions[bot]' are counted.
    Halts immediately if '[skip auto-heal]' is detected.
    """
    root = repo_root or get_repo_root()
    if not base_ref:
        base_ref = os.environ.get("GITHUB_BASE_REF", "")

    # Build git log command targeting PR range if base_ref is available
    log_cmd = ["git", "log", "--pretty=format:%an|%ae|%s"]
    if base_ref:
        test_code, _ = run_cmd(["git", "rev-parse", "--verify", f"origin/{base_ref}"], cwd=root)
        if test_code == 0:
            log_cmd.append(f"origin/{base_ref}..HEAD")
        else:
            test_code2, _ = run_cmd(["git", "rev-parse", "--verify", base_ref], cwd=root)
            if test_code2 == 0:
                log_cmd.append(f"{base_ref}..HEAD")
            else:
                log_cmd.extend(["-n", "10"])
    else:
        log_cmd.extend(["-n", "10"])

    code, out = run_cmd(log_cmd, cwd=root)
    if code != 0:
        # Fallback to recent commits
        code, out = run_cmd(["git", "log", "-n", "5", "--pretty=format:%an|%ae|%s"], cwd=root)
        if code != 0:
            code, out = run_cmd(["git", "log", "-n", "5", "--pretty=format:%s"], cwd=root)
            if code != 0:
                print(f"[self-heal] Warning: Git log check failed: {out}")
                return True

    count = 0
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            author_name, author_email, subject = parts
        else:
            author_name, author_email, subject = "", "", line

        if "[skip auto-heal]" in subject:
            print("[self-heal] Found '[skip auto-heal]' in commit history. Halting.")
            return False

        if "[auto-heal]" in subject or "fix(auto-heal)" in subject:
            # Anti-spoofing verification:
            # Only count as auto-heal attempt if authored by github-actions[bot]
            # (or if author metadata was not requested in legacy %s format)
            is_bot = (
                any(b in author_name.lower() for b in ["github-actions", "bot"]) or
                any(b in author_email.lower() for b in ["github-actions", "actions@github.com"]) or
                not author_name
            )
            if is_bot:
                count += 1
            else:
                print(f"[self-heal] Non-bot commit '{subject}' carried auto-heal marker (author: {author_name}). Ignored for loop guard.")

    print(f"[self-heal] PR auto-heal commits detected: {count}/{MAX_AUTO_HEAL_ATTEMPTS}")
    if count >= MAX_AUTO_HEAL_ATTEMPTS:
        print("[self-heal] Loop guard tripped. Halting to prevent runaway cycles.")
        return False
    return True


# ---------------------------------------------------------------------------
# JUnit XML Parser & Node ID Builder
# ---------------------------------------------------------------------------
def construct_pytest_node_id(test_file: str, classname: str, test_name: str) -> str:
    """
    Construct exact pytest node ID (e.g. tests/test_writer.py::TestClass::test_func[param]).
    Returns empty string if test_file is missing or empty.
    """
    if not test_file or not test_file.strip():
        return ""
    norm_file = test_file.replace("\\", "/").strip()
    file_stem = Path(norm_file).stem
    class_parts = classname.split(".") if classname else []

    # Identify if a class exists after the file stem in classname
    if file_stem in class_parts:
        idx = class_parts.index(file_stem)
        sub_classes = class_parts[idx + 1:]
    else:
        # Fallback: check last part if capitalized
        sub_classes = [c for c in class_parts[-1:] if c and c[0].isupper()]

    if sub_classes:
        return f"{norm_file}::{'::'.join(sub_classes)}::{test_name}"
    return f"{norm_file}::{test_name}"


def parse_junit_report(report_path: Path) -> dict[str, Any]:
    """Parse xunit1 JUnit XML report, supporting both <failure> and <error> elements."""
    if not report_path.exists():
        return {}

    failures = []
    has_collection_error = False
    try:
        tree = ET.parse(report_path)
        root = tree.getroot()
        for testcase in root.iter("testcase"):
            fail_els = testcase.findall("failure")
            err_els = testcase.findall("error")

            for el in fail_els + err_els:
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                file_attr = testcase.get("file", "")
                message = el.get("message", "")
                body = (el.text or "").strip()

                is_error = el.tag == "error"
                if is_error or not file_attr or not name or name == "collect":
                    has_collection_error = True

                node_id = construct_pytest_node_id(file_attr, classname, name) if (file_attr and name and not is_error) else ""

                failures.append({
                    "test": f"{classname}::{name}",
                    "name": name,
                    "classname": classname,
                    "file": file_attr,
                    "node_id": node_id,
                    "is_error": is_error,
                    "message": message,
                    "traceback": body[-3000:] if len(body) > 3000 else body
                })
    except Exception as e:
        print(f"[self-heal] Warning parsing JUnit XML: {e}")

    return {
        "failures": failures,
        "has_collection_error": has_collection_error
    }


# ---------------------------------------------------------------------------
# Failure Classification
# ---------------------------------------------------------------------------
def extract_final_exception_line(traceback_text: str, message_text: str) -> str:
    """Extract the final exception line from the traceback or message."""
    lines = [ln.strip() for ln in (traceback_text + "\n" + message_text).splitlines() if ln.strip()]
    if not lines:
        return ""
    # Search backwards for standard Python exception patterns (e.g. AssertionError, ConnectionError)
    for line in reversed(lines):
        if re.search(r"\b[A-Za-z_]+(?:Error|Exception|Failure)\b", line):
            return line
    return lines[-1]


def classify_failure(
    primary_failure: dict[str, Any],
    backend_cwd: Path,
    repo_root: Path | None = None
) -> tuple[str, str]:
    """
    Classify failure into FLAKY, NON_CODE, COLLECTION_ERROR, or CODE_BUG.
    Returns (classification_label, reason_description).
    """
    if primary_failure.get("is_error") or not primary_failure.get("node_id"):
        return "COLLECTION_ERROR", "Test suite encountered collection or module import error."

    node_id = primary_failure["node_id"]
    traceback_text = primary_failure.get("traceback", "")
    message_text = primary_failure.get("message", "")
    final_line = extract_final_exception_line(traceback_text, message_text)

    # 1. Non-Code / Infra error check on the FINAL exception line
    non_code_patterns = [
        r"ConnectionRefusedError",
        r"ConnectionError",
        r"NewConnectionError",
        r"MaxRetryError",
        r"socket\.gaierror",
        r"TimeoutError",
        r"OperationalError.*could not connect"
    ]
    for pat in non_code_patterns:
        if re.search(pat, final_line):
            return "NON_CODE", f"Infrastructure/network failure detected: {final_line}"

    # Missing env var
    if re.search(r"KeyError:.*(?:KEY|SECRET|TOKEN|URL|DATABASE)", final_line):
        return "NON_CODE", f"Missing environment variable detected: {final_line}"

    # Third-party vs local ModuleNotFoundError or ImportError
    mod_match = re.search(r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]", final_line)
    if mod_match:
        mod_name = mod_match.group(1)
        if not (mod_name.startswith("app") or mod_name.startswith("tests") or "backend" in mod_name):
            return "NON_CODE", f"Missing third-party dependency: {mod_name}"
        return "CODE_BUG", f"Local repository import error: {final_line}"

    imp_match = re.search(r"ImportError:\s*cannot import name ['\"][^'\"]+['\"]\s*from\s*(?:partially initialized module\s*)?['\"]([^'\"]+)['\"]", final_line)
    if imp_match:
        mod_name = imp_match.group(1)
        if not (mod_name.startswith("app") or mod_name.startswith("tests") or "backend" in mod_name):
            return "NON_CODE", f"Missing third-party dependency: {mod_name}"
        return "CODE_BUG", f"Local repository import error: {final_line}"

    # 2. Flaky Probe: Re-run failing node ID once under clean environment
    print(f"[self-heal] Running flaky probe on node ID: {node_id}...")
    py_exec = sys.executable
    rerun_code, rerun_out = run_cmd([py_exec, "-m", "pytest", node_id, "-q"], cwd=backend_cwd, timeout=STAGE1_TIMEOUT_SECONDS)
    if rerun_code == 0:
        return "FLAKY", f"Test passed on immediate re-run without code modification: {node_id}"

    # 3. Code Bug
    return "CODE_BUG", f"Confirmed test assertion/logic defect: {final_line}"


# ---------------------------------------------------------------------------
# Secret Redaction Engine
# ---------------------------------------------------------------------------
def redact_secrets(text: str, custom_env: dict[str, str] | None = None) -> str:
    """
    Redact API keys, tokens, auth headers, and sensitive environment variables.
    Preserves common system values (ports like 8000, localhost, paths).
    """
    env_to_scan = custom_env if custom_env is not None else os.environ

    # 1. Collect secrets from env vars matching KEY|TOKEN|SECRET|PASSWORD|AUTH with len >= 8
    secret_values = set()
    for k, v in env_to_scan.items():
        if SECRET_KEY_NAME_REGEX.search(k) and len(v) >= 8:
            secret_values.add(v)

    # Sort longest first to avoid partial replacements
    redacted = text
    for sec in sorted(secret_values, key=len, reverse=True):
        redacted = redacted.replace(sec, "[REDACTED_SECRET]")

    # 2. Regex pattern replacements
    for pat in SECRET_PATTERNS:
        redacted = pat.sub("[REDACTED_TOKEN]", redacted)

    return redacted


def file_contains_unredacted_secret(content: str, custom_env: dict[str, str] | None = None) -> bool:
    """Detect if a source file contains unredacted API keys or secrets before sending as context."""
    env_to_scan = custom_env if custom_env is not None else os.environ
    for k, v in env_to_scan.items():
        if SECRET_KEY_NAME_REGEX.search(k) and len(v) >= 12 and v in content:
            return True
    for pat in SECRET_PATTERNS[:5]:  # Specific regex patterns
        if pat.search(content):
            return True
    return False


# ---------------------------------------------------------------------------
# Patch Safety Policy & Byte-Level Verification
# ---------------------------------------------------------------------------
def validate_patch_target_path(resolved_path: Path, repo_root: Path, allow_test_edits: bool = False) -> tuple[bool, str]:
    """Validate that target path satisfies allowlist and anchored deny list."""
    try:
        rel_posix = resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return False, f"Target path {resolved_path} escapes repository root."

    # Check Anchored Deny List
    for prefix in ANCHORED_DENY_PREFIXES:
        if rel_posix.startswith(prefix):
            return False, f"Target path {rel_posix} violates anchored deny prefix '{prefix}'."

    # Check Forbidden Test Files
    for pat in FORBIDDEN_FILE_PATTERNS:
        if re.search(pat, rel_posix):
            if not allow_test_edits:
                return False, f"Target file {rel_posix} is a test/fixture file and test edits are disabled."

    # Check Allowlist
    if not rel_posix.startswith(ALLOWLIST_PREFIX) and not allow_test_edits:
        return False, f"Target path {rel_posix} is outside allowlist '{ALLOWLIST_PREFIX}'."

    return True, "Valid path."


def validate_patch_content(search_bytes: bytes, replace_bytes: bytes, original_bytes: bytes) -> tuple[bool, str]:
    """Validate search_block matching and ensure no assertion weakening or dangerous calls."""
    # Match count must be exactly 1
    matches = original_bytes.count(search_bytes)
    if matches == 0:
        return False, "search_block not found in target file."
    if matches > 1:
        return False, f"search_block matched {matches} times; ambiguous replacement rejected."

    replace_str = replace_bytes.decode("utf-8", errors="ignore")
    search_str = search_bytes.decode("utf-8", errors="ignore")

    # Check forbidden dangerous patterns
    for pat in FORBIDDEN_PATCH_PATTERNS:
        if re.search(pat, replace_str) and not re.search(pat, search_str):
            return False, f"Patch introduces forbidden pattern matching '{pat}'."

    # Check assertion weakening (removing assert statements)
    assert_removals = len(re.findall(r"\bassert\b", search_str)) - len(re.findall(r"\bassert\b", replace_str))
    if assert_removals > 0:
        return False, f"Patch weakens tests by removing {assert_removals} assert statement(s)."

    return True, "Valid patch content."


# ---------------------------------------------------------------------------
# Two-Stage Verification Gate
# ---------------------------------------------------------------------------
def verify_patch(
    node_id: str | None,
    backend_cwd: Path
) -> tuple[bool, str]:
    """
    Two-stage verification gate:
    Stage 1: Re-runs the exact failing node ID (30s timeout).
    Stage 2: Runs the hermetic regression suite (180s timeout).
    """
    py_exec = sys.executable

    # Stage 1: Targeted re-test
    if node_id:
        print(f"[self-heal] Stage 1: Running targeted verification on {node_id}...")
        stage1_code, stage1_out = run_cmd([py_exec, "-m", "pytest", node_id, "-q"], cwd=backend_cwd, timeout=STAGE1_TIMEOUT_SECONDS)
        if stage1_code != 0:
            return False, f"Stage 1 targeted verification failed (code {stage1_code}): {stage1_out[:300]}"
        print("[self-heal] Stage 1 targeted verification PASSED!")

    # Stage 2: Regression test suite
    print("[self-heal] Stage 2: Running hermetic regression suite...")
    stage2_cmd = [py_exec, "-m", "pytest", "-m", "not live and not network", "-q"]
    stage2_code, stage2_out = run_cmd(stage2_cmd, cwd=backend_cwd, timeout=STAGE2_TIMEOUT_SECONDS)
    if stage2_code != 0:
        return False, f"Stage 2 regression suite failed (code {stage2_code}): {stage2_out[:300]}"

    print("[self-heal] Stage 2 regression suite PASSED!")
    return True, "All verification checks passed."


# ---------------------------------------------------------------------------
# Context Building & PR Diff
# ---------------------------------------------------------------------------
def get_pr_diff(repo_root: Path, base_ref: str | None = None) -> str:
    """Fetch PR git diff relative to origin/{base_ref} or {base_ref}."""
    if not base_ref:
        base_ref = os.environ.get("GITHUB_BASE_REF", "main")
    code, out = run_cmd(["git", "diff", f"origin/{base_ref}...HEAD"], cwd=repo_root, timeout=15.0)
    if code != 0 or not out:
        code, out = run_cmd(["git", "diff", f"{base_ref}...HEAD"], cwd=repo_root, timeout=15.0)
    if code == 0 and out:
        if len(out) > 3000:
            return out[:3000] + "\n[...diff truncated...]"
        return out
    return ""


def build_llm_prompt(
    failure: dict[str, Any],
    candidate_paths: list[Path],
    repo_root: Path,
    prior_failure_feedback: str = "",
    base_ref: str | None = None
) -> str:
    """Construct capped and redacted prompt for the LLM."""
    context_blocks = []

    # Failing traceback
    context_blocks.append(f"### Failing Test Traceback:\n{failure.get('traceback', failure.get('message', ''))}")

    # Failing test source code
    if failure.get("file"):
        test_path = resolve_workspace_path(failure["file"], repo_root)
        if test_path and test_path.exists():
            test_content = test_path.read_text(encoding="utf-8", errors="ignore")
            context_blocks.append(f"### Test Source File ({failure['file']}):\n{test_content[:2500]}")

    # Implicated source files
    for p in candidate_paths[:MAX_PATCH_FILES]:
        if p.exists() and p.is_file():
            rel = p.relative_to(repo_root).as_posix()
            content = p.read_text(encoding="utf-8", errors="ignore")
            context_blocks.append(f"### Source File ({rel}):\n{content[:3000]}")

    # PR Diff
    diff = get_pr_diff(repo_root, base_ref=base_ref)
    if diff:
        context_blocks.append(f"### PR Git Diff:\n{diff}")

    # Prior feedback if retrying
    if prior_failure_feedback:
        context_blocks.append(f"### Feedback From Previous Attempt:\nYour prior patch failed verification:\n{prior_failure_feedback}\nPlease correct the issue.")

    full_context = "\n\n".join(context_blocks)
    redacted_context = redact_secrets(full_context)
    if len(redacted_context) > MAX_CONTEXT_CHARS:
        redacted_context = redacted_context[:MAX_CONTEXT_CHARS] + "\n... [Context Truncated to fit budget]"

    prompt = f"""A CI test failed on Pull Request.
{redacted_context}

Analyze the root cause and provide a surgical fix.
You MUST output ONLY a valid JSON object matching this schema:
{{
  "explanation": "concise description of root cause and fix",
  "patches": [
    {{
      "file_path": "backend/app/services/target.py",
      "search_block": "exact unique lines to replace",
      "replace_block": "replacement code"
    }}
  ]
}}
Do NOT include markdown formatting or conversational text. Return raw JSON only.
"""
    return prompt


# ---------------------------------------------------------------------------
# Phase 3 Workflow Integration & Git Operations
# ---------------------------------------------------------------------------
def verify_remote_head_unchanged(head_ref: str, expected_sha: str, repo_root: Path | None = None) -> tuple[bool, str]:
    """
    Query origin remote HEAD SHA via git ls-remote and assert it matches starting commit SHA.
    Prevents race conditions if a developer pushed new commits while self-heal was running.
    """
    if not head_ref or not expected_sha:
        return True, "No head_ref or expected_sha specified; skipping remote race check."

    root = repo_root or get_repo_root()
    code, out = run_cmd(["git", "ls-remote", "origin", f"refs/heads/{head_ref}"], cwd=root)
    if code != 0 or not out.strip():
        # Fallback query if refs/heads/ was omitted in ref lookup
        code2, out2 = run_cmd(["git", "ls-remote", "origin", head_ref], cwd=root)
        if code2 != 0 or not out2.strip():
            return False, f"Failed to query remote HEAD for '{head_ref}': {out}"
        out = out2

    first_line = out.strip().splitlines()[0]
    remote_sha = first_line.split()[0].strip()

    if remote_sha.lower() != expected_sha.lower():
        return False, (
            f"Race condition detected: remote branch '{head_ref}' moved during self-healing "
            f"(remote: {remote_sha[:7]}, expected: {expected_sha[:7]}). Aborting push."
        )

    return True, f"Remote HEAD matches expected SHA {expected_sha[:7]}."


def trigger_workflow_dispatch(repo: str, branch: str, token: str, workflow_file: str = "ci-cd.yml") -> tuple[bool, str]:
    """
    Trigger workflow_dispatch on ci-cd.yml via GitHub REST API.
    Used when pushing with default GITHUB_TOKEN so CI re-runs on the auto-heal commit.
    """
    if not (repo and branch and token):
        return False, "Missing repo, branch, or token for workflow_dispatch."

    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
    payload = json.dumps({"ref": branch}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DeepSeek-AutoHeal"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (204, 201, 200):
                return True, f"workflow_dispatch triggered successfully for branch '{branch}'."
            return False, f"workflow_dispatch returned status {resp.status}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        return False, f"workflow_dispatch HTTPError {e.code}: {body}"
    except Exception as e:
        return False, f"workflow_dispatch failed: {e}"


def push_and_trigger_ci(
    head_ref: str,
    expected_sha: str | None,
    repo_root: Path,
    gh_token: str,
    gh_repo: str,
    is_bot_token: bool = False
) -> tuple[bool, str]:
    """
    Safely push changes to head_ref and ensure CI re-runs.
    1. Verifies remote HEAD has not moved since job started (race prevention).
    2. Pushes HEAD to head_ref without force-push.
    3. If token is bot PAT/App token (is_bot_token=True), GitHub naturally triggers CI.
       If token is default GITHUB_TOKEN, triggers workflow_dispatch fallback.
    """
    if expected_sha:
        remote_ok, remote_msg = verify_remote_head_unchanged(head_ref, expected_sha, repo_root)
        if not remote_ok:
            return False, remote_msg

    # Push commit (never force-push)
    push_code, push_out = run_cmd(["git", "push", "origin", f"HEAD:{head_ref}"], cwd=repo_root)
    if push_code != 0:
        return False, f"Git push failed: {push_out}"

    # CI Re-triggering strategy
    if is_bot_token:
        return True, "Fix pushed using bot token. CI re-triggered automatically."
    else:
        # Fallback: Trigger workflow_dispatch so CI re-runs on the heal commit
        dispatch_ok, dispatch_msg = trigger_workflow_dispatch(gh_repo, head_ref, gh_token)
        if dispatch_ok:
            return True, f"Fix pushed. Workflow re-run triggered via dispatch ({dispatch_msg})."
        else:
            return True, f"Fix pushed. Notice: workflow_dispatch fallback status: {dispatch_msg}"


def format_pr_audit_comment(
    status: str,
    details: dict[str, Any]
) -> str:
    """
    Generate structured, rich markdown audit comments for GitHub PR review.
    Covers: PATCH_APPLIED, FLAKY, NON_CODE, COLLECTION_ERROR, LOOP_GUARD_TRIPPED,
    RACE_DETECTED, and general safety notices.
    """
    lines = []
    if status == "PATCH_APPLIED":
        explanation = details.get("explanation", "Automated bug repair")
        staged_paths = details.get("staged_paths", [])
        commit_msg = details.get("commit_msg", "")
        provider = details.get("provider", "Unknown")
        attempts = details.get("attempts", 1)
        node_id = details.get("node_id", "")
        lines.append("### 🤖 Autonomous Self-Healing Patch Applied")
        lines.append("")
        lines.append(f"> **Root Cause & Repair**: {explanation}")
        lines.append("")
        lines.append(f"- **Target Node**: `{node_id}`")
        lines.append(f"- **Patched Files**: `{', '.join(staged_paths)}`")
        lines.append(f"- **Provider**: `{provider}` (Attempt {attempts}/{MAX_ENGINE_ATTEMPTS})")
        lines.append("- **Verification**: Two-stage gate passed (exact failing test + hermetic regression suite).")
        lines.append(f"- **Commit**: `{commit_msg}`")
        lines.append("")
        lines.append("_Automated fix pushed by DeepSeek/Groq Autonomous Test Harness._")

    elif status == "FLAKY":
        node_id = details.get("node_id", "")
        lines.append("### ℹ️ Self-Healing Skipped: Flaky Test Detected")
        lines.append("")
        lines.append(f"- **Classification**: `FLAKY`")
        lines.append(f"- **Test Node**: `{node_id}`")
        lines.append(f"- **Detail**: The test failed in the initial test run but passed upon immediate clean re-run probe.")
        lines.append("- **Action**: Skipped LLM code repair to prevent masking intermittent test non-determinism.")

    elif status == "NON_CODE":
        reason = details.get("reason", "")
        lines.append("### ℹ️ Self-Healing Skipped: Infrastructure / Non-Code Failure")
        lines.append("")
        lines.append(f"- **Classification**: `NON_CODE`")
        lines.append(f"- **Reason**: {reason}")
        lines.append("- **Action**: Failure is attributed to external networking, missing service credentials, or third-party packages. No code repair applied.")

    elif status == "COLLECTION_ERROR":
        reason = details.get("reason", "")
        lines.append("### ⚠️ Self-Healing Skipped: Test Suite Collection Error")
        lines.append("")
        lines.append(f"- **Classification**: `COLLECTION_ERROR`")
        lines.append(f"- **Reason**: {reason}")
        lines.append("- **Action**: Pytest was unable to collect tests. Please verify imports, test syntax, and configuration.")

    elif status == "LOOP_GUARD_TRIPPED":
        limit = details.get("limit", MAX_AUTO_HEAL_ATTEMPTS)
        lines.append("### ⚠️ Self-Healing Skipped: Loop Guard Activated")
        lines.append("")
        lines.append(f"- **Status**: Maximum autonomous repair attempts ({limit}) reached for this PR range.")
        lines.append("- **Action**: Halting automated modifications to prevent runaway PR commits. Human review required.")

    elif status == "RACE_DETECTED":
        reason = details.get("reason", "")
        lines.append("### ⚠️ Self-Healing Aborted: Concurrent Remote Push Detected")
        lines.append("")
        lines.append(f"- **Status**: {reason}")
        lines.append("- **Action**: Remote branch moved while self-healing was running. Aborted push to avoid overwriting developer commits.")

    else:
        reason = details.get("reason", "Self-healing did not apply modifications.")
        lines.append(f"### ℹ️ Self-Healing Notice: {status}")
        lines.append("")
        lines.append(f"- **Details**: {reason}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GitHub PR Commenting & Metrics Logging
# ---------------------------------------------------------------------------
def post_github_comment(pr_number: str, message: str, token: str, repo: str) -> None:
    """Post audit comment to GitHub PR."""
    if not (pr_number and token and repo):
        return
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    clean_message = redact_secrets(message)
    req = urllib.request.Request(
        url,
        data=json.dumps({"body": clean_message}).encode("utf-8"),
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
        print(f"[self-heal] Notice: Could not post PR comment: {e}")


def write_metrics(metrics: dict[str, Any], repo_root: Path) -> None:
    """Save execution telemetry to reports/heal_metrics.json."""
    reports_dir = repo_root / "reports"
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        metrics_file = reports_dir / "heal_metrics.json"
        metrics_file.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"[self-heal] Telemetry metrics written to {metrics_file}")
    except Exception as e:
        print(f"[self-heal] Warning: Could not write metrics: {e}")


# ---------------------------------------------------------------------------
# Main Autonomous Loop
# ---------------------------------------------------------------------------
def main(
    provider: LLMProvider | None = None,
    allow_test_edits: bool = False,
    repo_root: Path | None = None,
    no_push: bool = False,
    push_only: bool = False
) -> int:
    start_time = time.time()
    if repo_root is None:
        repo_root = get_repo_root()

    backend_cwd = get_backend_cwd(repo_root)
    metrics: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "classification": "UNKNOWN",
        "rerun_result": "NOT_RUN",
        "success": False,
        "attempts": 0,
        "provider_used_per_attempt": [],
        "patch_size": {"files": 0, "lines_added": 0, "lines_removed": 0},
        "rejection_reasons": [],
        "verification_stages": {},
        "latency_seconds": 0.0,
        "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }

    head_ref = os.environ.get("GITHUB_HEAD_REF")
    base_ref = os.environ.get("GITHUB_BASE_REF")
    expected_sha = os.environ.get("GITHUB_HEAD_SHA")
    is_bot_token = os.environ.get("HEAL_BOT_TOKEN_CONFIGURED", "").lower() == "true"
    pr_number = os.environ.get("PR_NUMBER", "")
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "")

    # Mode 1: Dedicated Push-Only Step (Least Privilege: secrets only in push step)
    if push_only:
        print("[self-heal] Executing isolated push-only step...")
        metrics_file = repo_root / "reports" / "heal_metrics.json"
        metrics_data: dict[str, Any] = {}
        if metrics_file.exists():
            try:
                metrics_data = json.loads(metrics_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        push_token = os.environ.get("HEAL_BOT_TOKEN") or gh_token
        push_ok, push_msg = push_and_trigger_ci(
            head_ref=head_ref or "",
            expected_sha=expected_sha,
            repo_root=repo_root,
            gh_token=push_token,
            gh_repo=gh_repo,
            is_bot_token=is_bot_token
        )
        if push_ok:
            print(f"[self-heal] {push_msg}")
            explanation = metrics_data.get("explanation", "Automated bug repair")
            comment = format_pr_audit_comment("PATCH_APPLIED", {
                "explanation": explanation,
                "node_id": metrics_data.get("node_id", ""),
                "staged_paths": metrics_data.get("staged_paths", []),
                "commit_msg": metrics_data.get("commit_msg", "fix(auto-heal): automated repair [auto-heal]"),
                "provider": metrics_data.get("provider_used_per_attempt", ["unknown"])[-1] if metrics_data.get("provider_used_per_attempt") else "unknown",
                "attempts": metrics_data.get("attempts", 1)
            })
            post_github_comment(pr_number, comment, push_token, gh_repo)
            return 0
        else:
            print(f"[self-heal] Warning: Push-only failed: {push_msg}")
            if "Race condition" in push_msg:
                comment = format_pr_audit_comment("RACE_DETECTED", {"reason": push_msg})
                post_github_comment(pr_number, comment, push_token, gh_repo)
            return 1

    try:
        print("=== Autonomous CI/CD Self-Healing Agent Starting ===")

        if not head_ref:
            print("[self-heal] Not a pull_request event (GITHUB_HEAD_REF unset). Skipping.")
            metrics["classification"] = "SKIPPED_NOT_PR"
            return 0

        if not check_loop_guard(base_ref=base_ref, repo_root=repo_root):
            metrics["classification"] = "LOOP_GUARD_TRIPPED"
            comment = format_pr_audit_comment("LOOP_GUARD_TRIPPED", {"limit": MAX_AUTO_HEAL_ATTEMPTS})
            post_github_comment(pr_number, comment, gh_token, gh_repo)
            return 0

        junit_path = repo_root / "backend" / "reports" / "junit.xml"
        if not junit_path.exists():
            junit_path = repo_root / "reports" / "junit.xml"

        report_data = parse_junit_report(junit_path)
        failures = report_data.get("failures", [])
        if not failures:
            print("[self-heal] No test failures found in JUnit report. Skipping.")
            metrics["classification"] = "NO_FAILURES_FOUND"
            return 0

        primary_failure = failures[0]
        classification, class_reason = classify_failure(primary_failure, backend_cwd, repo_root)
        metrics["classification"] = classification
        metrics["classification_reason"] = class_reason
        print(f"[self-heal] Failure classified as {classification}: {class_reason}")

        if classification in ("FLAKY", "NON_CODE", "COLLECTION_ERROR"):
            comment = format_pr_audit_comment(
                classification,
                {"node_id": primary_failure.get("node_id", ""), "reason": class_reason}
            )
            post_github_comment(pr_number, comment, gh_token, gh_repo)
            return 0

        # Collect candidate source files
        candidate_paths: list[Path] = []
        if primary_failure.get("file"):
            resolved_test = resolve_workspace_path(primary_failure["file"], repo_root)
            if resolved_test:
                candidate_paths.append(resolved_test)

        # Detect source files mentioned in traceback
        for match in re.findall(r'([a-zA-Z0-9_\-\./\\]+\.(?:py|tsx|ts|js|jsx))', primary_failure.get("traceback", "")):
            resolved = resolve_workspace_path(match, repo_root)
            if resolved and resolved not in candidate_paths:
                candidate_paths.append(resolved)

        # Secret in source check
        for p in candidate_paths:
            content = p.read_text(encoding="utf-8", errors="ignore")
            if file_contains_unredacted_secret(content):
                msg = f"Source file {p.relative_to(repo_root)} contains unredacted secret. Aborting healing."
                metrics["rejection_reasons"].append(msg)
                print(f"[self-heal] {msg}")
                return 0

        if provider is None:
            provider = build_default_provider()

        # Engine Retry Loop (Max 3 attempts)
        prior_feedback = ""
        committed = False
        for attempt_idx in range(1, MAX_ENGINE_ATTEMPTS + 1):
            metrics["attempts"] = attempt_idx
            print(f"\n--- [self-heal] Execution Attempt {attempt_idx}/{MAX_ENGINE_ATTEMPTS} ---")

            prompt = build_llm_prompt(primary_failure, candidate_paths, repo_root, prior_feedback, base_ref=base_ref)

            try:
                raw_response, usage = provider.generate_patch(prompt)
                metrics["provider_used_per_attempt"].append(usage.get("provider_used", getattr(provider, "name", "unknown")))
                metrics["tokens"]["prompt_tokens"] += usage.get("prompt_tokens", 0)
                metrics["tokens"]["completion_tokens"] += usage.get("completion_tokens", 0)
                metrics["tokens"]["total_tokens"] += usage.get("total_tokens", 0)
            except Exception as e:
                err_msg = f"LLM provider error on attempt {attempt_idx}: {e}"
                metrics["rejection_reasons"].append(err_msg)
                print(f"[self-heal] {err_msg}")
                break

            # Parse JSON safely
            clean_resp = raw_response.strip()
            if clean_resp.startswith("```"):
                clean_resp = re.sub(r"^```[a-z]*\s*", "", clean_resp)
                clean_resp = re.sub(r"\s*```$", "", clean_resp)

            try:
                patch_data = json.loads(clean_resp)
            except Exception as e:
                err_msg = f"Invalid non-JSON response from LLM: {e}"
                metrics["rejection_reasons"].append(err_msg)
                prior_feedback = f"Output was not valid JSON: {clean_resp[:200]}"
                continue

            # Standardize patch list
            raw_patches = patch_data.get("patches", [])
            if not raw_patches and patch_data.get("file_path"):
                raw_patches = [patch_data]

            explanation = patch_data.get("explanation", "Automated bug repair")

            if not raw_patches or len(raw_patches) > MAX_PATCH_FILES:
                err_msg = f"Invalid patch count ({len(raw_patches)})"
                metrics["rejection_reasons"].append(err_msg)
                prior_feedback = err_msg
                continue

            # Step A: Validate all patches first without modifying disk
            validation_failed = False
            validated_targets: list[tuple[Path, bytes, bytes, bytes]] = []

            for p_item in raw_patches:
                raw_f = p_item.get("file_path", "")
                resolved_f = resolve_workspace_path(raw_f, repo_root)
                if not resolved_f:
                    metrics["rejection_reasons"].append(f"Cannot resolve target path: {raw_f}")
                    prior_feedback = f"Cannot resolve file_path '{raw_f}'"
                    validation_failed = True
                    break

                path_ok, path_msg = validate_patch_target_path(resolved_f, repo_root, allow_test_edits)
                if not path_ok:
                    metrics["rejection_reasons"].append(path_msg)
                    prior_feedback = path_msg
                    validation_failed = True
                    break

                search_b = p_item.get("search_block", "").encode("utf-8")
                replace_b = p_item.get("replace_block", "").encode("utf-8")
                orig_b = resolved_f.read_bytes()

                content_ok, content_msg = validate_patch_content(search_b, replace_b, orig_b)
                if not content_ok:
                    metrics["rejection_reasons"].append(content_msg)
                    prior_feedback = content_msg
                    validation_failed = True
                    break

                validated_targets.append((resolved_f, search_b, replace_b, orig_b))

            if validation_failed:
                continue

            # Step B: Apply patches atomically (CRLF-safe byte replacement)
            print(f"[self-heal] Applying {len(validated_targets)} validated patch(es) to disk...")
            for resolved_f, search_b, replace_b, orig_b in validated_targets:
                patched_b = orig_b.replace(search_b, replace_b, 1)
                resolved_f.write_bytes(patched_b)

            # Step C: Two-Stage Verification Gate
            passed, verify_msg = verify_patch(primary_failure.get("node_id"), backend_cwd)
            metrics["verification_stages"][f"attempt_{attempt_idx}"] = "PASSED" if passed else "FAILED"

            if not passed:
                print(f"[self-heal] Verification failed: {verify_msg}. Restoring files...")
                for resolved_f, _, _, orig_b in validated_targets:
                    resolved_f.write_bytes(orig_b)
                prior_feedback = verify_msg
                continue

            # Verification succeeded!
            print("[self-heal] All verification checks passed! Staging and committing changes...")
            metrics["patch_size"]["files"] = len(validated_targets)
            run_cmd(["git", "config", "user.name", "github-actions[bot]"], cwd=repo_root)
            run_cmd(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=repo_root)

            # Stage only validated patched files (never git add -A)
            staged_paths = [t[0].relative_to(repo_root).as_posix() for t in validated_targets]
            run_cmd(["git", "add"] + staged_paths, cwd=repo_root)

            commit_msg = f"fix(auto-heal): {explanation} [auto-heal]"
            run_cmd(["git", "commit", "-m", commit_msg], cwd=repo_root)

            # Record commit metadata into metrics
            metrics["explanation"] = explanation
            metrics["commit_msg"] = commit_msg
            metrics["staged_paths"] = staged_paths
            metrics["node_id"] = primary_failure.get("node_id", "")

            # If running in --no-push mode (Step 4 least privilege separation)
            if no_push:
                print(f"[self-heal] Changes staged and committed locally ({commit_msg}). Skipping push (--no-push active).")
                gh_output = os.environ.get("GITHUB_OUTPUT")
                if gh_output:
                    try:
                        with open(gh_output, "a", encoding="utf-8") as f:
                            f.write("healed=true\n")
                            f.write(f"commit_msg={commit_msg}\n")
                    except Exception as e:
                        print(f"[self-heal] Notice: Could not write to GITHUB_OUTPUT: {e}")
                metrics["success"] = True
                committed = True
                break

            push_ok, push_msg = push_and_trigger_ci(
                head_ref=head_ref,
                expected_sha=expected_sha,
                repo_root=repo_root,
                gh_token=gh_token,
                gh_repo=gh_repo,
                is_bot_token=is_bot_token
            )

            if push_ok:
                print(f"[self-heal] {push_msg}")
                provider_name = metrics["provider_used_per_attempt"][-1] if metrics["provider_used_per_attempt"] else "unknown"
                comment = format_pr_audit_comment("PATCH_APPLIED", {
                    "explanation": explanation,
                    "node_id": primary_failure.get("node_id", ""),
                    "staged_paths": staged_paths,
                    "commit_msg": commit_msg,
                    "provider": provider_name,
                    "attempts": attempt_idx
                })
                post_github_comment(pr_number, comment, gh_token, gh_repo)
                committed = True
            else:
                print(f"[self-heal] Warning: Git push aborted or failed: {push_msg}")
                metrics["rejection_reasons"].append(push_msg)
                if "Race condition" in push_msg:
                    metrics["classification"] = "RACE_DETECTED"
                    comment = format_pr_audit_comment("RACE_DETECTED", {"reason": push_msg})
                    post_github_comment(pr_number, comment, gh_token, gh_repo)

            break

        metrics["success"] = committed
        return 0 if committed else 1

    except Exception as exc:
        metrics["classification"] = "ENGINE_CRASH"
        metrics["crash_error"] = str(exc)
        print(f"[self-heal] Unexpected engine crash: {exc}")
        return 1

    finally:
        metrics["latency_seconds"] = round(time.time() - start_time, 2)
        write_metrics(metrics, repo_root)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous CI/CD Self-Healing Agent")
    parser.add_argument("--no-push", action="store_true", help="Diagnose, patch, verify, and commit locally without pushing to remote.")
    parser.add_argument("--push-only", action="store_true", help="Push the already verified local heal commit and trigger CI/post PR comment.")
    parser.add_argument("--allow-test-edits", action="store_true", help="Allow patches targeting test files (disabled in CI).")
    args = parser.parse_args()
    sys.exit(main(allow_test_edits=args.allow_test_edits, no_push=args.no_push, push_only=args.push_only))
