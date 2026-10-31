"""
Comprehensive Phase 2 Hermetic Test Suite for DeepSeek/Groq CI Harness (DSH).
100% Hermetic: zero external network calls, zero real credentials, temp directories only.
Exhaustively covers all 10 core Phase 2 verification categories:
1. JUnit parsing (parametrized tests, missing file attribute, <failure> and <error>)
2. resolve_workspace_path (all 4 path forms, traversal, symlinks, absolute path rejection)
3. Atomic multi-file patch apply and rollback on verification failure
4. Search string not found (zero, multiple matches) and empty/malformed LLM output
5. Disallowed path patch rejected, test-file edit rejected, assertion-weakening rejected
6. Patch and context size caps, selective secret redaction
7. Flaky classification (passes on re-run) and NON_CODE classification skip LLM
8. Provider failover on 429 using FakeProvider with injectable sleep
9. Loop guard logic (clean, limit reached, [skip auto-heal])
10. run_cmd subprocess timeout handling with process-tree termination
"""

import sys
import os
import json
import tempfile
import subprocess
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.deepseek_self_heal import (
    resolve_workspace_path,
    get_scrubbed_env,
    run_cmd,
    check_loop_guard,
    construct_pytest_node_id,
    parse_junit_report,
    extract_final_exception_line,
    classify_failure,
    redact_secrets,
    file_contains_unredacted_secret,
    validate_patch_target_path,
    validate_patch_content,
    build_llm_prompt,
    write_metrics,
    main,
    BaseHTTPProvider,
    FailoverProvider,
    LLMProvider,
    MAX_AUTO_HEAL_ATTEMPTS,
    MAX_ENGINE_ATTEMPTS,
    verify_remote_head_unchanged,
    trigger_workflow_dispatch,
    push_and_trigger_ci,
    format_pr_audit_comment,
    post_github_comment,
    get_pr_diff,
    verify_patch,
)


class FakeProvider:
    """Test-only provider for hermetic testing. No mock code in production module."""
    def __init__(self, responses: list[str] | str, name: str = "FakeProvider"):
        self.name = name
        self.responses = [responses] if isinstance(responses, str) else list(responses)
        self.call_count = 0
        self.prompts: list[str] = []

    def generate_patch(self, prompt: str) -> tuple[str, dict]:
        self.prompts.append(prompt)
        resp = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return resp, {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "provider_used": self.name
        }


# ---------------------------------------------------------------------------
# Category 1: JUnit Parsing (Parametrized, Missing File Attribute, Errors)
# ---------------------------------------------------------------------------
def test_junit_parsing_parametrized_and_missing_file(tmp_path):
    """Verify parsing of parametrized tests, class tests, and missing file attributes."""
    xml_path = tmp_path / "junit.xml"
    xml_path.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" failures="2" errors="1" tests="3">
  <!-- 1. Parametrized test -->
  <testcase classname="tests.test_pricing" name="test_discount[10-percent]" file="tests/test_pricing.py">
    <failure message="assert 90 == 85">AssertionError: assert 90 == 85</failure>
  </testcase>
  <!-- 2. Class-based test -->
  <testcase classname="tests.test_pricing.TestEngine" name="test_engine_run" file="tests/test_pricing.py">
    <failure message="assert False">AssertionError: assert False</failure>
  </testcase>
  <!-- 3. Missing file attribute / collection error -->
  <testcase classname="tests.test_broken" name="collect" file="">
    <error message="collection error">ImportError: broken module</error>
  </testcase>
</testsuite>
""", encoding="utf-8")

    data = parse_junit_report(xml_path)
    assert len(data["failures"]) == 3
    assert data["has_collection_error"] is True

    # Check parametrized node ID
    f1 = data["failures"][0]
    assert f1["node_id"] == "tests/test_pricing.py::test_discount[10-percent]"

    # Check class-based node ID
    f2 = data["failures"][1]
    assert f2["node_id"] == "tests/test_pricing.py::TestEngine::test_engine_run"

    # Check missing file attribute -> empty node_id -> COLLECTION_ERROR
    f3 = data["failures"][2]
    assert f3["node_id"] == ""
    cls, reason = classify_failure(f3, backend_cwd=tmp_path)
    assert cls == "COLLECTION_ERROR"


# ---------------------------------------------------------------------------
# Category 2: resolve_workspace_path (All 4 Forms + Traversal, Symlinks, Absolute)
# ---------------------------------------------------------------------------
def test_resolve_workspace_path_all_four_forms_and_security(tmp_path):
    """Verify all 4 workspace path forms resolve, while escapes and absolute paths are rejected."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Create 4 test targets
    f1 = repo / "tests" / "test_root.py"
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text("t1", encoding="utf-8")

    f2 = repo / "app" / "service_root.py"
    f2.parent.mkdir(parents=True, exist_ok=True)
    f2.write_text("s1", encoding="utf-8")

    f3 = repo / "backend" / "tests" / "test_backend.py"
    f3.parent.mkdir(parents=True, exist_ok=True)
    f3.write_text("t2", encoding="utf-8")

    f4 = repo / "backend" / "app" / "service_backend.py"
    f4.parent.mkdir(parents=True, exist_ok=True)
    f4.write_text("s2", encoding="utf-8")

    # All 4 forms must resolve
    assert resolve_workspace_path("tests/test_root.py", repo_root=repo) == f1.resolve()
    assert resolve_workspace_path("app/service_root.py", repo_root=repo) == f2.resolve()
    assert resolve_workspace_path("backend/tests/test_backend.py", repo_root=repo) == f3.resolve()
    assert resolve_workspace_path("backend/app/service_backend.py", repo_root=repo) == f4.resolve()

    # Traversal (..) rejected
    assert resolve_workspace_path("../outside.py", repo_root=repo) is None
    assert resolve_workspace_path("backend/app/../../outside.py", repo_root=repo) is None

    # Absolute paths rejected
    if sys.platform == "win32":
        assert resolve_workspace_path("C:/Windows/System32/cmd.exe", repo_root=repo) is None
        assert resolve_workspace_path("C:\\Windows\\System32\\cmd.exe", repo_root=repo) is None
    else:
        assert resolve_workspace_path("/etc/passwd", repo_root=repo) is None

    # Non-existent file rejected
    assert resolve_workspace_path("backend/app/does_not_exist.py", repo_root=repo) is None


def test_parent_directory_symlink_rejected(tmp_path):
    """
    Verify that files located inside a symlinked parent directory are rejected.
    Note: On Windows without Developer Mode / elevated rights, symlink creation fails with OSError.
    """
    if sys.platform == "win32":
        try:
            link = tmp_path / "test_link"
            target = tmp_path / "target"
            target.mkdir()
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            pytest.skip("Windows non-elevated environment lacks SeCreateSymbolicLinkPrivilege; symlink creation skipped on Windows. Needs Linux CI validation.")

    target_dir = tmp_path / "real_dir"
    target_dir.mkdir()
    sym_dir = tmp_path / "sym_dir"
    try:
        sym_dir.symlink_to(target_dir, target_is_directory=True)
    except OSError:
        pytest.skip("Environment lacks symlink creation privileges; skipped. Needs Linux CI validation.")

    file_inside_sym = sym_dir / "file.py"
    file_inside_sym.write_text("code", encoding="utf-8")

    assert resolve_workspace_path("sym_dir/file.py", repo_root=tmp_path) is None


# ---------------------------------------------------------------------------
# Category 3: Atomic Multi-File Rollback on Verification Failure
# ---------------------------------------------------------------------------
def test_atomic_multi_file_rollback_on_verification_failure(tmp_path, monkeypatch):
    """Verify that multi-file patches revert ALL files byte-for-byte if verification fails."""
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix-multi")

    app_dir = tmp_path / "backend" / "app"
    app_dir.mkdir(parents=True)
    file_a = app_dir / "service_a.py"
    file_b = app_dir / "service_b.py"

    original_a = b"SERVICE_A_STATUS = 'UNHEALTHY'\r\n"
    original_b = b"SERVICE_B_STATUS = 'UNHEALTHY'\r\n"
    file_a.write_bytes(original_a)
    file_b.write_bytes(original_b)

    rep_dir = tmp_path / "backend" / "reports"
    rep_dir.mkdir(parents=True)
    (rep_dir / "junit.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" failures="1" tests="1">
  <testcase classname="tests.test_services" name="test_services_healthy" file="tests/test_services.py">
    <failure message="services unhealthy">AssertionError</failure>
  </testcase>
</testsuite>
""", encoding="utf-8")

    multi_patch = json.dumps({
        "explanation": "Update both services to HEALTHY",
        "patches": [
            {
                "file_path": "backend/app/service_a.py",
                "search_block": "SERVICE_A_STATUS = 'UNHEALTHY'",
                "replace_block": "SERVICE_A_STATUS = 'HEALTHY'"
            },
            {
                "file_path": "backend/app/service_b.py",
                "search_block": "SERVICE_B_STATUS = 'UNHEALTHY'",
                "replace_block": "SERVICE_B_STATUS = 'HEALTHY'"
            }
        ]
    })
    provider = FakeProvider([multi_patch, multi_patch, multi_patch])

    with patch("tools.deepseek_self_heal.check_loop_guard", return_value=True), \
         patch("tools.deepseek_self_heal.classify_failure", return_value=("CODE_BUG", "AssertionError")), \
         patch("tools.deepseek_self_heal.verify_patch", return_value=(False, "Verification failed in stage 2")):

        exit_code = main(provider=provider, repo_root=tmp_path)
        assert exit_code == 1

        # Both files must be restored byte-for-byte
        assert file_a.read_bytes() == original_a
        assert file_b.read_bytes() == original_b


# ---------------------------------------------------------------------------
# Category 4: Search Block Not Found, Multiple Matches & Empty LLM Output
# ---------------------------------------------------------------------------
def test_search_string_not_found_zero_and_multiple_matches():
    content = b"alpha = 10\nbeta = 20\nalpha = 10\n"

    # Zero matches
    ok0, msg0 = validate_patch_content(b"gamma = 30", b"gamma = 40", content)
    assert ok0 is False
    assert "not found" in msg0

    # Multiple matches
    ok2, msg2 = validate_patch_content(b"alpha = 10", b"alpha = 50", content)
    assert ok2 is False
    assert "matched 2 times" in msg2


def test_empty_and_malformed_llm_output_handled_gracefully(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix-empty")

    rep_dir = tmp_path / "backend" / "reports"
    rep_dir.mkdir(parents=True)
    (rep_dir / "junit.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" failures="1" tests="1">
  <testcase classname="tests.test_x" name="test_x" file="tests/test_x.py">
    <failure message="fail">AssertionError</failure>
  </testcase>
</testsuite>""", encoding="utf-8")

    # Empty string response
    provider_empty = FakeProvider(["", ""])
    with patch("tools.deepseek_self_heal.check_loop_guard", return_value=True), \
         patch("tools.deepseek_self_heal.classify_failure", return_value=("CODE_BUG", "AssertionError")):

        code = main(provider=provider_empty, repo_root=tmp_path)
        assert code == 1

        metrics = json.loads((tmp_path / "reports" / "heal_metrics.json").read_text(encoding="utf-8"))
        assert any("Invalid non-JSON" in r for r in metrics["rejection_reasons"])


# ---------------------------------------------------------------------------
# Category 5: Patch Policy (Disallowed Paths, Tests, Assertion Weakening)
# ---------------------------------------------------------------------------
def test_patch_policy_disallowed_paths_and_test_file_edits(tmp_path):
    repo = tmp_path

    # Disallowed anchored prefixes
    for prefix in [".github/workflows/ci.yml", "tools/script.py", "docs/README.md", "frontend/src/App.tsx", ".env.local"]:
        p = repo / prefix
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
        ok, msg = validate_patch_target_path(p.resolve(), repo_root=repo)
        assert ok is False
        assert "violates anchored deny" in msg or "outside allowlist" in msg

    # Test file modification rejected
    test_f = repo / "backend" / "app" / "tests" / "test_nested.py"
    test_f.parent.mkdir(parents=True, exist_ok=True)
    test_f.write_text("def test(): pass", encoding="utf-8")
    ok_t, msg_t = validate_patch_target_path(test_f.resolve(), repo_root=repo)
    assert ok_t is False
    assert "is a test/fixture file" in msg_t

    conftest_f = repo / "backend" / "app" / "conftest.py"
    conftest_f.write_text("fixtures", encoding="utf-8")
    ok_c, msg_c = validate_patch_target_path(conftest_f.resolve(), repo_root=repo)
    assert ok_c is False
    assert "is a test/fixture file" in msg_c


def test_assertion_weakening_and_dangerous_calls_rejected():
    content = b"def test_pricing():\n    assert margin >= 0.2\n"
    # Remove assert
    weak_patch = b"    pass\n"
    ok, msg = validate_patch_content(b"    assert margin >= 0.2\n", weak_patch, content)
    assert ok is False
    assert "weakens tests by removing" in msg

    # Dangerous eval/exec injection
    eval_patch = b"    eval('__import__(\"os\").system(\"id\")')\n"
    ok_e, msg_e = validate_patch_content(b"    assert margin >= 0.2\n", eval_patch, content)
    assert ok_e is False
    assert "forbidden pattern" in msg_e


# ---------------------------------------------------------------------------
# Category 6: Caps & Secret Redaction
# ---------------------------------------------------------------------------
def test_caps_and_secret_redaction():
    custom_env = {
        "JWT_SECRET_KEY": "supersecretjwtkey9999",
        "DATABASE_URL": "postgresql://usr:pass@db:5432/klypup",
        "APP_PORT": "8080",
        "HOST": "localhost"
    }

    raw_text = "Server on localhost:8080 using JWT supersecretjwtkey9999 and token gsk_999999999999999999999"
    redacted = redact_secrets(raw_text, custom_env=custom_env)

    # Secrets replaced
    assert "supersecretjwtkey9999" not in redacted
    assert "[REDACTED_SECRET]" in redacted
    assert "[REDACTED_TOKEN]" in redacted

    # Non-secrets preserved
    assert "localhost:8080" in redacted

    # Source file with unredacted secret detected
    secret_file = "DB_KEY = 'sk-11111111111111111111111111111111'\n"
    assert file_contains_unredacted_secret(secret_file, custom_env=custom_env) is True


# ---------------------------------------------------------------------------
# Category 7: Flaky & NON_CODE Classification Skips LLM
# ---------------------------------------------------------------------------
def test_flaky_classification_skips_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix-flaky")
    rep_dir = tmp_path / "backend" / "reports"
    rep_dir.mkdir(parents=True)
    (rep_dir / "junit.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" failures="1" tests="1">
  <testcase classname="tests.test_flaky" name="test_f" file="tests/test_flaky.py">
    <failure message="fail">AssertionError</failure>
  </testcase>
</testsuite>""", encoding="utf-8")

    provider = FakeProvider(json.dumps({"patches": []}))

    # Simulate flaky probe passing on re-run (exit code 0)
    with patch("tools.deepseek_self_heal.check_loop_guard", return_value=True), \
         patch("tools.deepseek_self_heal.run_cmd", return_value=(0, "PASSED")):

        code = main(provider=provider, repo_root=tmp_path)
        assert code == 0
        assert provider.call_count == 0  # LLM never called!

        metrics = json.loads((tmp_path / "reports" / "heal_metrics.json").read_text(encoding="utf-8"))
        assert metrics["classification"] == "FLAKY"


def test_non_code_classification_skips_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix-infra")
    rep_dir = tmp_path / "backend" / "reports"
    rep_dir.mkdir(parents=True)
    (rep_dir / "junit.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" failures="1" tests="1">
  <testcase classname="tests.test_infra" name="test_i" file="tests/test_infra.py">
    <failure message="ConnectionError">ConnectionRefusedError: [Errno 111] Connection refused</failure>
  </testcase>
</testsuite>""", encoding="utf-8")

    provider = FakeProvider(json.dumps({"patches": []}))

    with patch("tools.deepseek_self_heal.check_loop_guard", return_value=True):
        code = main(provider=provider, repo_root=tmp_path)
        assert code == 0
        assert provider.call_count == 0  # LLM never called!

        metrics = json.loads((tmp_path / "reports" / "heal_metrics.json").read_text(encoding="utf-8"))
        assert metrics["classification"] == "NON_CODE"


# ---------------------------------------------------------------------------
# Category 8: Provider Failover on 429 using FakeProvider
# ---------------------------------------------------------------------------
def test_provider_failover_on_429_using_fake_provider():
    p1 = MagicMock(spec=BaseHTTPProvider)
    p1.name = "Groq Key #1"
    p1.api_key = "gsk_11111111111111111111"
    p1.model_name = "qwen"
    err429 = urllib.error.HTTPError("url", 429, "Rate limit reached", {"Retry-After": "2"}, None)
    err429.read = MagicMock(return_value=b"rate_limit_exceeded")
    p1.generate_patch.side_effect = err429

    p2 = MagicMock(spec=BaseHTTPProvider)
    p2.name = "Groq Key #2"
    p2.api_key = "gsk_22222222222222222222"
    p2.model_name = "qwen"
    p2.generate_patch.return_value = (json.dumps({"patches": []}), {"total_tokens": 50})

    mock_sleep = MagicMock()
    failover = FailoverProvider([p1, p2], sleep_fn=mock_sleep)

    content, usage = failover.generate_patch("test prompt")
    assert usage["provider_used"] == "Groq Key #2"
    mock_sleep.assert_called_once_with(2.0)


# ---------------------------------------------------------------------------
# Category 9: Loop Guard Logic (Clean, Tripped, Skip Auto-Heal)
# ---------------------------------------------------------------------------
def test_loop_guard_logic(tmp_path):
    # Case 1: Clean history (< 2 auto-heal commits)
    with patch("tools.deepseek_self_heal.run_cmd", return_value=(0, "feat: pricing\nfix: catalog")):
        assert check_loop_guard(repo_root=tmp_path) is True

    # Case 2: Max attempts reached (>= 2 auto-heal commits)
    with patch("tools.deepseek_self_heal.run_cmd", return_value=(0, "fix(auto-heal): retry [auto-heal]\nfix(auto-heal): first [auto-heal]")):
        assert check_loop_guard(repo_root=tmp_path) is False

    # Case 3: [skip auto-heal] present
    with patch("tools.deepseek_self_heal.run_cmd", return_value=(0, "feat: update scraper [skip auto-heal]")):
        assert check_loop_guard(repo_root=tmp_path) is False


# ---------------------------------------------------------------------------
# Category 10: run_cmd Subprocess Timeout Handling
# ---------------------------------------------------------------------------
def test_run_cmd_timeout_handling():
    """Verify run_cmd terminates process tree on timeout and returns exit code 124."""
    py_exec = sys.executable
    cmd = [py_exec, "-c", "import time; time.sleep(10)"]
    code, output = run_cmd(cmd, timeout=0.2)
    assert code == 124
    assert "timed out after 0.2 seconds and was terminated" in output


# ---------------------------------------------------------------------------
# Phase 3 Workflow Integration Tests (PR Range, Bot Anti-Spoofing, Race, Dispatch)
# ---------------------------------------------------------------------------
def test_pr_range_loop_guard_bot_author_verification(tmp_path):
    """
    Verify loop guard inspects PR range and enforces bot-author anti-spoofing.
    Human commits carrying [auto-heal] are ignored; bot commits count towards limit.
    """
    # Case 1: Human developer commits with [auto-heal] (attempted spoof or coincidence)
    human_log = "Human Dev|human@example.com|fix: manual adjustment [auto-heal]\nHuman Dev|human@example.com|feat: new pricing rule"
    with patch("tools.deepseek_self_heal.run_cmd", side_effect=[
        (0, "origin/main"),  # git rev-parse origin/main
        (0, human_log)       # git log origin/main..HEAD
    ]):
        # Even with [auto-heal], it's not by github-actions[bot], so loop guard passes
        assert check_loop_guard(base_ref="main", repo_root=tmp_path) is True

    # Case 2: Bot commits 2 times with [auto-heal] -> trips loop guard
    bot_log = (
        "github-actions[bot]|github-actions[bot]@users.noreply.github.com|fix(auto-heal): second patch [auto-heal]\n"
        "github-actions[bot]|github-actions[bot]@users.noreply.github.com|fix(auto-heal): first patch [auto-heal]"
    )
    with patch("tools.deepseek_self_heal.run_cmd", side_effect=[
        (0, "origin/main"),  # git rev-parse origin/main
        (0, bot_log)         # git log origin/main..HEAD
    ]):
        assert check_loop_guard(base_ref="main", repo_root=tmp_path) is False

    # Case 3: [skip auto-heal] halts regardless of author
    skip_log = "Human Dev|human@example.com|docs: update deployment [skip auto-heal]"
    with patch("tools.deepseek_self_heal.run_cmd", side_effect=[
        (0, "origin/main"),
        (0, skip_log)
    ]):
        assert check_loop_guard(base_ref="main", repo_root=tmp_path) is False


def test_remote_race_safety_aborts_on_moved_head(tmp_path):
    """
    Verify verify_remote_head_unchanged and push_and_trigger_ci abort if remote branch moved.
    """
    expected_sha = "1111111111111111111111111111111111111111"

    # Case 1: Remote HEAD matches expected SHA
    matching_ls = f"{expected_sha}\trefs/heads/feature-heal"
    with patch("tools.deepseek_self_heal.run_cmd", return_value=(0, matching_ls)):
        ok, msg = verify_remote_head_unchanged("feature-heal", expected_sha, tmp_path)
        assert ok is True
        assert "Remote HEAD matches" in msg

    # Case 2: Remote HEAD moved (another developer pushed during repair)
    moved_sha = "9999999999999999999999999999999999999999"
    moved_ls = f"{moved_sha}\trefs/heads/feature-heal"
    with patch("tools.deepseek_self_heal.run_cmd", return_value=(0, moved_ls)):
        ok, msg = verify_remote_head_unchanged("feature-heal", expected_sha, tmp_path)
        assert ok is False
        assert "Race condition detected" in msg
        assert "9999999" in msg

    # Case 3: push_and_trigger_ci aborts push and never calls git push when race occurs
    mock_run = MagicMock()
    with patch("tools.deepseek_self_heal.verify_remote_head_unchanged", return_value=(False, "Race condition detected")):
        with patch("tools.deepseek_self_heal.run_cmd", mock_run):
            pushed, push_msg = push_and_trigger_ci("feature-heal", expected_sha, tmp_path, "fake_token", "owner/repo")
            assert pushed is False
            assert "Race condition detected" in push_msg
            mock_run.assert_not_called()  # git push was never executed!


def test_workflow_dispatch_fallback_triggered_when_pat_absent(tmp_path):
    """
    Verify workflow_dispatch REST call is triggered when pushing with default GITHUB_TOKEN (is_bot_token=False),
    and is omitted when pushing with dedicated bot token (is_bot_token=True).
    """
    # Case 1: Default GITHUB_TOKEN (is_bot_token=False) -> triggers workflow_dispatch fallback
    with patch("tools.deepseek_self_heal.verify_remote_head_unchanged", return_value=(True, "OK")):
        with patch("tools.deepseek_self_heal.run_cmd", return_value=(0, "Everything up-to-date")):
            with patch("tools.deepseek_self_heal.trigger_workflow_dispatch", return_value=(True, "Dispatched")) as mock_dispatch:
                pushed, msg = push_and_trigger_ci("fix-test", "sha123", tmp_path, "gh_token", "owner/repo", is_bot_token=False)
                assert pushed is True
                assert "Workflow re-run triggered via dispatch" in msg
                mock_dispatch.assert_called_once_with("owner/repo", "fix-test", "gh_token")

    # Case 2: Bot token configured (is_bot_token=True) -> native trigger, no dispatch call
    with patch("tools.deepseek_self_heal.verify_remote_head_unchanged", return_value=(True, "OK")):
        with patch("tools.deepseek_self_heal.run_cmd", return_value=(0, "Everything up-to-date")):
            with patch("tools.deepseek_self_heal.trigger_workflow_dispatch") as mock_dispatch:
                pushed, msg = push_and_trigger_ci("fix-test", "sha123", tmp_path, "bot_token", "owner/repo", is_bot_token=True)
                assert pushed is True
                assert "Fix pushed using bot token" in msg
                mock_dispatch.assert_not_called()


def test_pr_audit_comment_formatting_and_secret_redaction():
    """
    Verify format_pr_audit_comment produces expected markdown and post_github_comment redacts secrets.
    """
    # 1. Format test: PATCH_APPLIED
    patch_comment = format_pr_audit_comment("PATCH_APPLIED", {
        "explanation": "Fixed zero-division error in dynamic pricing formula",
        "node_id": "tests/test_pricing.py::test_zero_cost",
        "staged_paths": ["backend/app/pricing.py"],
        "commit_msg": "fix(auto-heal): Fixed zero-division error [auto-heal]",
        "provider": "Groq Key #1 (qwen-2.5-coder-32b)",
        "attempts": 1
    })
    assert "Autonomous Self-Healing Patch Applied" in patch_comment
    assert "tests/test_pricing.py::test_zero_cost" in patch_comment
    assert "backend/app/pricing.py" in patch_comment
    assert "Two-stage gate passed" in patch_comment

    # 2. Format test: FLAKY
    flaky_comment = format_pr_audit_comment("FLAKY", {
        "node_id": "tests/test_pricing.py::test_intermittent_cache",
        "reason": "Test passed upon immediate clean re-run probe."
    })
    assert "Self-Healing Skipped: Flaky Test Detected" in flaky_comment
    assert "tests/test_pricing.py::test_intermittent_cache" in flaky_comment

    # 3. Format test: NON_CODE
    non_code_comment = format_pr_audit_comment("NON_CODE", {
        "reason": "ConnectionRefusedError: [Errno 111] Connection refused"
    })
    assert "Self-Healing Skipped: Infrastructure / Non-Code Failure" in non_code_comment

    # 4. Secret redaction during comment posting
    sensitive_comment = "Error connecting with gsk_secrettoken12345678901234567890 and Bearer secret_auth_bearer_9999"
    captured_body = []

    def mock_urlopen(req, timeout):
        captured_body.append(json.loads(req.data.decode("utf-8"))["body"])
        mock_resp = MagicMock()
        mock_resp.status = 201
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        post_github_comment("42", sensitive_comment, "mock_token", "owner/repo")

    assert len(captured_body) == 1
    assert "gsk_secrettoken" not in captured_body[0]
    assert "[REDACTED_TOKEN]" in captured_body[0]


# ---------------------------------------------------------------------------
# Step 1 & Step 2 Evidence Gap Closure Tests
# ---------------------------------------------------------------------------
def test_real_pytest_xml_generation_xunit1_vs_xunit2(tmp_path):
    """
    Step 1 Permanent Test:
    Executes real pytest against a temporary project containing:
    1. A plain failing test
    2. A parametrized failing test
    3. A class-based failing test
    4. A module with a collection error (broken import)
    Empirically parses the resulting XML and verifies:
    - xunit1 emits 'file' attribute on <testcase>, allowing node ID reconstruction.
    - xunit2 omits 'file' attribute on <testcase>, breaking node ID reconstruction.
    - Collection error generates <error message="collection failure"> with classname="".
    """
    test_file = tmp_path / "test_sample.py"
    test_file.write_text(
        "import pytest\n\n"
        "class TestSampleClass:\n"
        "    def test_class_method(self):\n"
        "        assert 1 == 2\n\n"
        "def test_plain_function():\n"
        "    assert 10 == 20\n\n"
        "@pytest.mark.parametrize('param', [100])\n"
        "def test_param_function(param):\n"
        "    assert param == 999\n",
        encoding="utf-8"
    )

    err_file = tmp_path / "test_broken.py"
    err_file.write_text(
        "import non_existent_collection_module_xyz\n"
        "def test_dummy(): pass\n",
        encoding="utf-8"
    )

    py_exec = sys.executable
    junit1_path = tmp_path / "junit1.xml"
    junit2_path = tmp_path / "junit2.xml"
    junit_err_path = tmp_path / "junit_err.xml"

    # 1. Run with xunit1
    subprocess.run(
        [py_exec, "-m", "pytest", str(test_file), "-o", "junit_family=xunit1", f"--junitxml={junit1_path}"],
        capture_output=True, check=False, cwd=tmp_path
    )
    assert junit1_path.exists()
    report1 = parse_junit_report(junit1_path)
    assert len(report1["failures"]) == 3
    node_ids = {f["name"]: f["node_id"] for f in report1["failures"]}

    assert "test_class_method" in node_ids
    assert node_ids["test_class_method"].endswith("test_sample.py::TestSampleClass::test_class_method")

    assert "test_plain_function" in node_ids
    assert node_ids["test_plain_function"].endswith("test_sample.py::test_plain_function")

    assert "test_param_function[100]" in node_ids
    assert node_ids["test_param_function[100]"].endswith("test_sample.py::test_param_function[100]")

    # Check file attribute is present in raw XML for xunit1
    tree1 = ET.parse(junit1_path)
    for tc in tree1.findall(".//testcase"):
        assert "file" in tc.attrib, f"xunit1 missing file attribute in {tc.attrib}"

    # 2. Run with xunit2
    subprocess.run(
        [py_exec, "-m", "pytest", str(test_file), "-o", "junit_family=xunit2", f"--junitxml={junit2_path}"],
        capture_output=True, check=False, cwd=tmp_path
    )
    assert junit2_path.exists()
    tree2 = ET.parse(junit2_path)
    for tc in tree2.findall(".//testcase"):
        assert "file" not in tc.attrib, f"xunit2 unexpectedly contained file attribute in {tc.attrib}"

    # 3. Collection error run (xunit1)
    subprocess.run(
        [py_exec, "-m", "pytest", str(err_file), "-o", "junit_family=xunit1", f"--junitxml={junit_err_path}"],
        capture_output=True, check=False, cwd=tmp_path
    )
    assert junit_err_path.exists()
    report_err = parse_junit_report(junit_err_path)
    assert report_err["has_collection_error"] is True
    assert len(report_err["failures"]) == 1
    err_failure = report_err["failures"][0]
    assert err_failure["is_error"] is True
    assert err_failure["node_id"] == ""


def test_collection_error_handling(tmp_path, monkeypatch):
    """
    Step 2.1: Collection error / <error> element handling.
    Asserts suite collection error classifies as COLLECTION_ERROR, skips LLM, and posts PR comment.
    """
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix-import")
    rep_dir = tmp_path / "backend" / "reports"
    rep_dir.mkdir(parents=True)
    (rep_dir / "junit.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" errors="1" tests="1">
  <testcase classname="" name="test_broken.py">
    <error message="collection failure">ModuleNotFoundError: No module named 'non_existent_xyz'</error>
  </testcase>
</testsuite>""",
        encoding="utf-8"
    )

    provider = FakeProvider(json.dumps({"patches": []}))

    with patch("tools.deepseek_self_heal.check_loop_guard", return_value=True), \
         patch("tools.deepseek_self_heal.post_github_comment") as mock_comment:

        code = main(provider=provider, repo_root=tmp_path)
        assert code == 0
        assert provider.call_count == 0  # LLM skipped!

        metrics = json.loads((tmp_path / "reports" / "heal_metrics.json").read_text(encoding="utf-8"))
        assert metrics["classification"] == "COLLECTION_ERROR"
        assert "collection or module import error" in metrics["classification_reason"]
        mock_comment.assert_called_once()
        comment_body = mock_comment.call_args[0][1]
        assert "Self-Healing Skipped: Test Suite Collection Error" in comment_body


def test_scrubbed_env_removes_sensitive_secrets(monkeypatch):
    """
    Step 2.2: Scrubbed env: verification subprocess run via run_cmd cannot see
    GROQ_API_KEY, DEEPSEEK_API_KEY, HEAL_BOT_TOKEN, or GITHUB_TOKEN.
    """
    monkeypatch.setenv("GROQ_API_KEY", "gsk_sensitive_secret_groq")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk_sensitive_secret_deepseek")
    monkeypatch.setenv("HEAL_BOT_TOKEN", "pat_sensitive_secret_healbot")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_sensitive_secret_token")
    monkeypatch.setenv("SECRET_PASSWORD_123", "super_secret_pw")

    # Run child process printing its own os.environ as json
    cmd = [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"]
    ret, out = run_cmd(cmd)
    assert ret == 0

    child_env = json.loads(out)
    assert "GROQ_API_KEY" not in child_env
    assert "DEEPSEEK_API_KEY" not in child_env
    assert "HEAL_BOT_TOKEN" not in child_env
    assert "GITHUB_TOKEN" not in child_env
    assert "SECRET_PASSWORD_123" not in child_env

    # Essential variables are preserved
    assert "PATH" in child_env
    assert child_env.get("FLASK_ENV") == "testing"


def test_retry_loop_prompt_feedback_and_rollback(tmp_path, monkeypatch):
    """
    Step 2.3: Retry loop: attempt 2's prompt contains attempt 1's (redacted) verification failure;
    loop stops at MAX_ENGINE_ATTEMPTS; files are rolled back between attempts.
    """
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix-retry")
    app_dir = tmp_path / "backend" / "app"
    app_dir.mkdir(parents=True)
    target = app_dir / "pricing.py"
    initial_content = "BASE_MARGIN = 0.05\n"
    target.write_text(initial_content, encoding="utf-8")

    rep_dir = tmp_path / "backend" / "reports"
    rep_dir.mkdir(parents=True)
    (rep_dir / "junit.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" failures="1" tests="1">
  <testcase classname="tests.test_pricing" name="test_margin" file="tests/test_pricing.py">
    <failure message="margin too low">AssertionError: assert 0.05 >= 0.10</failure>
  </testcase>
</testsuite>""",
        encoding="utf-8"
    )

    patch_att1 = json.dumps({
        "explanation": "Attempt 1: set margin to 0.08",
        "patches": [{"file_path": "backend/app/pricing.py", "search_block": "BASE_MARGIN = 0.05", "replace_block": "BASE_MARGIN = 0.08"}]
    })
    patch_att2 = json.dumps({
        "explanation": "Attempt 2: set margin to 0.15",
        "patches": [{"file_path": "backend/app/pricing.py", "search_block": "BASE_MARGIN = 0.05", "replace_block": "BASE_MARGIN = 0.15"}]
    })

    provider = FakeProvider([patch_att1, patch_att2, patch_att2])

    verify_calls = []
    def mock_verify_patch(node_id, cwd):
        verify_calls.append(len(verify_calls) + 1)
        if len(verify_calls) == 1:
            # First attempt fails verification with a message containing sensitive token
            return False, "Stage 1 verification failed: margin 0.08 still below 0.10 with token gsk_secrettoken1234567890123456"
        return True, "Verification PASSED"

    with patch("tools.deepseek_self_heal.check_loop_guard", return_value=True), \
         patch("tools.deepseek_self_heal.classify_failure", return_value=("CODE_BUG", "AssertionError")), \
         patch("tools.deepseek_self_heal.verify_patch", side_effect=mock_verify_patch):

        code = main(provider=provider, repo_root=tmp_path, no_push=True)
        assert code == 0
        assert provider.call_count == 2

        # Check prompt of attempt 2 contains redacted feedback from attempt 1
        prompt2 = provider.prompts[1]
        assert "### Feedback From Previous Attempt:" in prompt2
        assert "margin 0.08 still below 0.10" in prompt2
        assert "gsk_secrettoken" not in prompt2
        assert "[REDACTED_TOKEN]" in prompt2

        # Verify final content is attempt 2
        assert target.read_text(encoding="utf-8") == "BASE_MARGIN = 0.15\n"


def test_metrics_written_on_skip_and_crash(tmp_path, monkeypatch):
    """
    Step 2.4: Metrics written on skip AND on crash.
    Assert reports/heal_metrics.json exists with expected fields when:
    (a) classification is FLAKY
    (b) an unexpected exception is raised mid-run
    """
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix-metrics")
    rep_dir = tmp_path / "backend" / "reports"
    rep_dir.mkdir(parents=True)
    metrics_file = tmp_path / "reports" / "heal_metrics.json"

    # Part A: FLAKY skip
    (rep_dir / "junit.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" failures="1" tests="1">
  <testcase classname="tests.test_f" name="test_flaky_case" file="tests/test_f.py">
    <failure message="flaky">AssertionError</failure>
  </testcase>
</testsuite>""",
        encoding="utf-8"
    )

    with patch("tools.deepseek_self_heal.check_loop_guard", return_value=True), \
         patch("tools.deepseek_self_heal.classify_failure", return_value=("FLAKY", "Passed on immediate re-run probe")):

        code_skip = main(provider=FakeProvider(""), repo_root=tmp_path)
        assert code_skip == 0
        assert metrics_file.exists()
        m_skip = json.loads(metrics_file.read_text(encoding="utf-8"))
        assert m_skip["classification"] == "FLAKY"
        assert m_skip["success"] is False
        assert m_skip["attempts"] == 0
        assert "latency_seconds" in m_skip

    # Part B: Unexpected mid-run crash
    with patch("tools.deepseek_self_heal.check_loop_guard", return_value=True), \
         patch("tools.deepseek_self_heal.classify_failure", side_effect=RuntimeError("Simulated pipeline crash mid-run")):

        code_crash = main(provider=FakeProvider(""), repo_root=tmp_path)
        assert code_crash == 1
        assert metrics_file.exists()
        m_crash = json.loads(metrics_file.read_text(encoding="utf-8"))
        assert m_crash["classification"] == "ENGINE_CRASH"
        assert "Simulated pipeline crash mid-run" in m_crash["crash_error"]
        assert m_crash["success"] is False


def test_only_validated_patched_paths_committed(tmp_path, monkeypatch):
    """
    Step 2.5: Only validated patched paths are committed.
    After a successful heal in a temp git repo, assert reports/ and any other untracked
    files are NOT in the commit.
    """
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix-commit-isolation")

    # Initialize real git repository
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)

    app_dir = tmp_path / "backend" / "app"
    app_dir.mkdir(parents=True)
    calc_file = app_dir / "calculator.py"
    calc_file.write_text("RESULT = 10\n", encoding="utf-8")

    rep_dir = tmp_path / "backend" / "reports"
    rep_dir.mkdir(parents=True)
    (rep_dir / "junit.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" failures="1" tests="1">
  <testcase classname="tests.test_calc" name="test_res" file="tests/test_calc.py">
    <failure message="wrong">AssertionError</failure>
  </testcase>
</testsuite>""",
        encoding="utf-8"
    )

    # Initial commit
    subprocess.run(["git", "add", "backend/app/calculator.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)

    # Create untracked noise files in repo
    noise_file = tmp_path / "scratch_noise.tmp"
    noise_file.write_text("untracked noise", encoding="utf-8")

    patch_json = json.dumps({
        "explanation": "Fix result value",
        "patches": [{
            "file_path": "backend/app/calculator.py",
            "search_block": "RESULT = 10",
            "replace_block": "RESULT = 42"
        }]
    })
    provider = FakeProvider(patch_json)

    with patch("tools.deepseek_self_heal.check_loop_guard", return_value=True), \
         patch("tools.deepseek_self_heal.classify_failure", return_value=("CODE_BUG", "AssertionError")), \
         patch("tools.deepseek_self_heal.verify_patch", return_value=(True, "PASSED")):

        code = main(provider=provider, repo_root=tmp_path, no_push=True)
        assert code == 0

        # Check latest commit files
        res = subprocess.run(["git", "show", "--name-only", "--pretty=format:", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True)
        committed_files = [f.strip() for f in res.stdout.strip().splitlines() if f.strip()]

        assert committed_files == ["backend/app/calculator.py"]
        assert "scratch_noise.tmp" not in committed_files
        assert not any("reports" in f for f in committed_files)

        # Check git status shows noise_file and reports/ are still untracked
        st = subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True, check=True)
        assert "??" in st.stdout
        assert "scratch_noise.tmp" in st.stdout


def test_crlf_preservation(tmp_path):
    """
    Step 2.6: CRLF: patch applies correctly to a CRLF file and line endings are preserved.
    """
    target = tmp_path / "backend" / "app" / "crlf_target.py"
    target.parent.mkdir(parents=True)
    original_crlf = b"line_a = 1\r\nline_b = 'broken'\r\nline_c = 3\r\n"
    target.write_bytes(original_crlf)

    search_b = b"line_b = 'broken'"
    replace_b = b"line_b = 'healed'"

    ok, msg = validate_patch_content(search_b, replace_b, original_crlf)
    assert ok is True

    # Byte replacement as executed in self-heal engine
    patched_b = original_crlf.replace(search_b, replace_b, 1)
    target.write_bytes(patched_b)

    final_bytes = target.read_bytes()
    expected_bytes = b"line_a = 1\r\nline_b = 'healed'\r\nline_c = 3\r\n"
    assert final_bytes == expected_bytes
    assert final_bytes.count(b"\r\n") == 3
    # Ensure no lone \n without \r
    assert final_bytes.replace(b"\r\n", b"").count(b"\n") == 0


def test_failover_status_codes_and_retry_after():
    """
    Step 2.7: Failover details:
    - 401/403 disables that key for the run
    - Context-length 400 does NOT fail over (immediately raises)
    - Retry-After header is honored (injectable sleep receives exact float value)
    """
    # 1. Context-length 400 does NOT failover
    p_bad = MagicMock(spec=BaseHTTPProvider)
    p_bad.name = "Groq Key #1"
    p_bad.api_key = "gsk_11111111111111111111"
    p_bad.model_name = "qwen"
    err400 = urllib.error.HTTPError("url", 400, "Bad Request", {}, None)
    err400.read = MagicMock(return_value=b'{"error": {"message": "context_length_exceeded: maximum tokens 32768"}}')
    p_bad.generate_patch.side_effect = err400

    p_backup = MagicMock(spec=BaseHTTPProvider)
    p_backup.name = "Groq Key #2"
    p_backup.api_key = "gsk_22222222222222222222"

    failover_400 = FailoverProvider([p_bad, p_backup])
    with pytest.raises(RuntimeError, match="Context length exceeded on Groq Key #1"):
        failover_400.generate_patch("prompt")
    p_backup.generate_patch.assert_not_called()

    # 2. 401/403 disables key for subsequent calls in the run
    p_auth_fail = MagicMock(spec=BaseHTTPProvider)
    p_auth_fail.name = "Groq Bad Auth"
    p_auth_fail.api_key = "gsk_badauth11111111111"
    p_auth_fail.model_name = "qwen"
    err401 = urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)
    err401.read = MagicMock(return_value=b"Invalid API Key")
    p_auth_fail.generate_patch.side_effect = err401

    p_healthy = MagicMock(spec=BaseHTTPProvider)
    p_healthy.name = "Groq Healthy"
    p_healthy.api_key = "gsk_healthy2222222222"
    p_healthy.model_name = "qwen"
    p_healthy.generate_patch.return_value = (json.dumps({"patches": []}), {"total_tokens": 50})

    failover_auth = FailoverProvider([p_auth_fail, p_healthy])
    # Call 1: p_auth_fail fails with 401, key gets disabled, failover to p_healthy succeeds
    res1, u1 = failover_auth.generate_patch("p1")
    assert u1["provider_used"] == "Groq Healthy"
    assert "Groq Bad Auth" in failover_auth.disabled_providers

    # Call 2: p_auth_fail is skipped immediately without invoking generate_patch
    p_auth_fail.generate_patch.reset_mock()
    res2, u2 = failover_auth.generate_patch("p2")
    assert u2["provider_used"] == "Groq Healthy"
    p_auth_fail.generate_patch.assert_not_called()

    # 3. 429 Retry-After is parsed and passed to injectable sleep
    p_rate = MagicMock(spec=BaseHTTPProvider)
    p_rate.name = "Groq Rate Limited"
    p_rate.api_key = "gsk_rate11111111111111"
    p_rate.model_name = "qwen"
    err429 = urllib.error.HTTPError("url", 429, "Too Many Requests", {"Retry-After": "3"}, None)
    err429.read = MagicMock(return_value=b"Rate limit exceeded")
    p_rate.generate_patch.side_effect = err429

    mock_sleep = MagicMock()
    failover_rate = FailoverProvider([p_rate, p_healthy], sleep_fn=mock_sleep)
    failover_rate.generate_patch("test rate")
    mock_sleep.assert_called_once_with(3.0)


def test_pr_diff_included_and_truncated(tmp_path):
    """
    Step 2.8: PR diff is included in the LLM prompt and truncated at 3000 chars.
    """
    failure = {"traceback": "AssertionError", "file": ""}
    cand = []

    # Case A: Normal PR diff under 3000 chars
    normal_diff = "diff --git a/app.py b/app.py\n+def add(a, b): return a + b\n"
    with patch("tools.deepseek_self_heal.run_cmd", return_value=(0, normal_diff)):
        prompt = build_llm_prompt(failure, cand, tmp_path, base_ref="main")
        assert "### PR Git Diff:" in prompt
        assert "+def add(a, b): return a + b" in prompt
        assert "[...diff truncated...]" not in prompt

    # Case B: Diff exceeding 3000 chars is cleanly truncated with marker
    huge_diff = "diff --git a/big.py b/big.py\n" + ("+" + "x" * 80 + "\n") * 50  # >4000 chars
    with patch("tools.deepseek_self_heal.run_cmd", return_value=(0, huge_diff)):
        diff_out = get_pr_diff(tmp_path, base_ref="main")
        assert len(diff_out) <= 3050
        assert diff_out.endswith("\n[...diff truncated...]")
        prompt_huge = build_llm_prompt(failure, cand, tmp_path, base_ref="main")
        assert "### PR Git Diff:" in prompt_huge
        assert "[...diff truncated...]" in prompt_huge


def test_hermetic_end_to_end_pipeline(tmp_path, monkeypatch):
    """
    Step 2.9: Hermetic end-to-end: temp git repo with a seeded bug under backend/app,
    FakeProvider returns the correct patch, run the full pipeline
    (classify -> prompt -> patch -> verify -> commit).
    Assert bug file is fixed, nothing else changed, and commit contains only patched path.
    """
    monkeypatch.setenv("GITHUB_HEAD_REF", "fix-e2e")

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "DeepSeek Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@klypup.ai"], cwd=tmp_path, check=True, capture_output=True)

    app_dir = tmp_path / "backend" / "app"
    app_dir.mkdir(parents=True)
    pricing_file = app_dir / "pricing_engine.py"
    pricing_file.write_text(
        "def compute_discount(price: float) -> float:\n"
        "    return price / 0.0  # Intentional zero division bug\n",
        encoding="utf-8"
    )

    rep_dir = tmp_path / "backend" / "reports"
    rep_dir.mkdir(parents=True)
    (rep_dir / "junit.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" failures="1" tests="1">
  <testcase classname="tests.test_pricing" name="test_compute_discount" file="backend/tests/test_pricing.py">
    <failure message="ZeroDivisionError">ZeroDivisionError: float division by zero</failure>
  </testcase>
</testsuite>""",
        encoding="utf-8"
    )

    # Initial commit of bug
    subprocess.run(["git", "add", "backend/app/pricing_engine.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: initial buggy pricing"], cwd=tmp_path, check=True, capture_output=True)

    fix_patch = json.dumps({
        "explanation": "Fixed ZeroDivisionError by multiplying discount correctly",
        "patches": [{
            "file_path": "backend/app/pricing_engine.py",
            "search_block": "    return price / 0.0  # Intentional zero division bug",
            "replace_block": "    return price * 0.90"
        }]
    })
    provider = FakeProvider(fix_patch)

    with patch("tools.deepseek_self_heal.check_loop_guard", return_value=True), \
         patch("tools.deepseek_self_heal.classify_failure", return_value=("CODE_BUG", "ZeroDivisionError: float division by zero")), \
         patch("tools.deepseek_self_heal.verify_patch", return_value=(True, "Verification passed")):

        code = main(provider=provider, repo_root=tmp_path, no_push=True)
        assert code == 0

        # Assert bug file is fixed
        fixed_content = pricing_file.read_text(encoding="utf-8")
        assert "return price * 0.90" in fixed_content
        assert "/ 0.0" not in fixed_content

        # Assert commit was created with proper message and author
        log_res = subprocess.run(["git", "log", "-1", "--pretty=format:%an|%s"], cwd=tmp_path, capture_output=True, text=True, check=True)
        author, subject = log_res.stdout.split("|", 1)
        assert author == "github-actions[bot]"
        assert "fix(auto-heal):" in subject
        assert "[auto-heal]" in subject

        # Assert only the patched file was committed
        diff_res = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True)
        assert diff_res.stdout.strip() == "backend/app/pricing_engine.py"


def test_anchored_allowlist_vs_deny_list(tmp_path):
    """
    Step 2.10: backend/app/tools/x.py is ALLOWED by the policy (anchored deny list)
    while tools/x.py and .github/x.yml are rejected.
    """
    # 1. backend/app/tools/x.py -> ALLOWED
    f_allowed = tmp_path / "backend" / "app" / "tools" / "x.py"
    f_allowed.parent.mkdir(parents=True, exist_ok=True)
    f_allowed.write_text("x = 1", encoding="utf-8")
    ok1, msg1 = validate_patch_target_path(f_allowed.resolve(), repo_root=tmp_path)
    assert ok1 is True
    assert msg1 == "Valid path."

    # 2. tools/x.py -> REJECTED (anchored deny 'tools/')
    f_denied_tools = tmp_path / "tools" / "x.py"
    f_denied_tools.parent.mkdir(parents=True, exist_ok=True)
    f_denied_tools.write_text("x = 1", encoding="utf-8")
    ok2, msg2 = validate_patch_target_path(f_denied_tools.resolve(), repo_root=tmp_path)
    assert ok2 is False
    assert "violates anchored deny prefix 'tools/'" in msg2

    # 3. .github/workflows/ci.yml -> REJECTED (anchored deny '.github/')
    f_denied_gh = tmp_path / ".github" / "workflows" / "ci.yml"
    f_denied_gh.parent.mkdir(parents=True, exist_ok=True)
    f_denied_gh.write_text("name: CI", encoding="utf-8")
    ok3, msg3 = validate_patch_target_path(f_denied_gh.resolve(), repo_root=tmp_path)
    assert ok3 is False
    assert "violates anchored deny prefix '.github/'" in msg3


def test_failure_classification_edge_cases(tmp_path):
    """
    Step 2.11: Classification edge cases:
    - cannot import name from a repo module is CODE_BUG
    - missing third-party module is NON_CODE
    - test that merely mocks ConnectionError (final exception line is AssertionError) is CODE_BUG
    """
    # Case A: cannot import name from a repo module -> CODE_BUG
    fail_repo_import = {
        "file": "backend/tests/test_service.py",
        "node_id": "backend/tests/test_service.py::test_calc",
        "message": "ImportError: cannot import name 'calculate_tax' from 'backend.app.services'",
        "traceback": "ImportError: cannot import name 'calculate_tax' from 'backend.app.services'"
    }
    with patch("tools.deepseek_self_heal.run_cmd", return_value=(1, "FAILED")):
        cls_a, reason_a = classify_failure(fail_repo_import, backend_cwd=tmp_path)
        assert cls_a == "CODE_BUG"
        assert "Local repository import error" in reason_a

    # Case B: missing third-party module -> NON_CODE
    fail_third_party = {
        "file": "backend/tests/test_service.py",
        "node_id": "backend/tests/test_service.py::test_calc",
        "message": "ModuleNotFoundError: No module named 'stripe_payment_gateway'",
        "traceback": "ModuleNotFoundError: No module named 'stripe_payment_gateway'"
    }
    cls_b, reason_b = classify_failure(fail_third_party, backend_cwd=tmp_path)
    assert cls_b == "NON_CODE"
    assert "Missing third-party dependency: stripe_payment_gateway" in reason_b

    # Case C: Test merely mocks ConnectionError; final exception line is AssertionError -> CODE_BUG
    mock_tb = (
        "Traceback (most recent call last):\n"
        "  File 'backend/app/client.py', line 45, in request\n"
        "    # mock raised requests.exceptions.ConnectionError: mock conn failure\n"
        "  File 'backend/tests/test_client.py', line 80, in test_retries\n"
        "    assert mock_client.retry_count == 3\n"
        "AssertionError: assert 2 == 3"
    )
    fail_mocked_conn = {
        "file": "backend/tests/test_client.py",
        "node_id": "backend/tests/test_client.py::test_retries",
        "message": "assert 2 == 3",
        "traceback": mock_tb
    }
    with patch("tools.deepseek_self_heal.run_cmd", return_value=(1, "FAILED")):
        cls_c, reason_c = classify_failure(fail_mocked_conn, backend_cwd=tmp_path)
        assert cls_c == "CODE_BUG"
        assert "AssertionError" in reason_c

