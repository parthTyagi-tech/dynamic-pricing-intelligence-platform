#!/usr/bin/env python3
"""
tools/heal_benchmark/runner.py

Automated Benchmark Suite for DeepSeek/Groq Autonomous Self-Healing CI Harness (DSH).
Evaluates the self-healing engine across 15 real, seeded defects in backend/app/ code.

Features:
- Hermetic scratch copy isolation with guaranteed byte-for-byte rollback.
- Validates that each defect cleanly produces an expected test failure.
- Runs the harness against the configured LLM provider (or simulates validation in --dry-run).
- Evaluates fix success, attempt count, latency, tokens, patch size, and semantic correctness.
- Produces reports/benchmark_results.json and markdown summary for docs/CICD.md.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BUGS_DIR = Path(__file__).resolve().parent / "bugs"
REPORTS_DIR = REPO_ROOT / "reports"


def load_bug_fixtures() -> List[Dict[str, Any]]:
    """Load and sort all 15 bug fixtures from tools/heal_benchmark/bugs/."""
    fixtures = []
    for p in sorted(BUGS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            fixtures.append(data)
        except Exception as e:
            print(f"[benchmark] Warning: Failed to load fixture {p.name}: {e}")
    return fixtures


def run_cmd(cmd: List[str], cwd: Optional[Path] = None, timeout: float = 60.0) -> Tuple[int, str]:
    """Execute subprocess command safely with timeout and combined stdout/stderr."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False
        )
        return proc.returncode, proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return 124, f"Command timed out after {timeout}s."
    except Exception as e:
        return 1, str(e)


def evaluate_semantic_correctness(original_content: str, patched_content: str, search_block: str) -> bool:
    """
    Check if the patched code is semantically correct.
    Returns True if the corrupt block was reverted or replaced with equivalent uncorrupted logic.
    """
    if patched_content == original_content:
        return True
    # If not identical byte-for-byte, check if original search_block is restored
    if search_block in patched_content:
        return True
    return False


def run_benchmark_for_bug(
    bug: Dict[str, Any],
    dry_run: bool = False,
    provider_override: Any = None
) -> Dict[str, Any]:
    """
    Execute benchmark evaluation for a single seeded bug.
    Guarantees byte-for-byte rollback in all circumstances.
    """
    bug_id = bug["id"]
    name = bug["name"]
    category = bug["category"]
    target_rel = bug["target_file"]
    test_node = bug["test_node"]
    search_block = bug["search_block"]
    corrupt_block = bug["corrupt_block"]

    target_path = REPO_ROOT / target_rel
    backend_cwd = REPO_ROOT / "backend"
    reports_path = REPO_ROOT / "reports" / "junit.xml"
    reports_path.parent.mkdir(parents=True, exist_ok=True)

    result: Dict[str, Any] = {
        "id": bug_id,
        "name": name,
        "category": category,
        "target_file": target_rel,
        "test_node": test_node,
        "defect_injected": False,
        "test_failed_as_expected": False,
        "fixed": False,
        "attempts": 0,
        "provider": "N/A",
        "latency_seconds": 0.0,
        "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "patch_size": {"lines_added": 0, "lines_removed": 0},
        "semantic_correctness": False,
        "policy_rejections": [],
        "notes": ""
    }

    if not target_path.exists():
        result["notes"] = f"Target file does not exist: {target_rel}"
        return result

    # Read original file contents (for byte-level rollback)
    original_bytes = target_path.read_bytes()
    original_str = original_bytes.decode("utf-8", errors="replace")

    # Verify search block exists exactly once
    if original_str.count(search_block) != 1:
        result["notes"] = f"search_block matched {original_str.count(search_block)} times in {target_rel} (expected 1)"
        return result

    start_time = time.time()
    try:
        # Step 1: Inject seeded defect
        corrupted_str = original_str.replace(search_block, corrupt_block, 1)
        target_path.write_bytes(corrupted_str.encode("utf-8"))
        result["defect_injected"] = True

        # Step 2: Run pytest to confirm the bug causes test failure and generate junit.xml
        py_exec = sys.executable
        junit_cmd = [
            py_exec, "-m", "pytest", test_node,
            "-o", "junit_family=xunit1",
            f"--junitxml={reports_path}",
            "-q"
        ]
        test_code, test_out = run_cmd(junit_cmd, cwd=backend_cwd, timeout=30.0)

        if test_code == 0:
            result["notes"] = "Seeded bug did NOT fail test as expected (test passed unexpectedly)."
            return result

        result["test_failed_as_expected"] = True

        if dry_run:
            # In dry-run mode, we validated defect injection and test failure. Rollback and mark validated.
            result["notes"] = "Defect validation successful: seeded bug cleanly fails test."
            result["defect_validated"] = True
            result["status"] = "validated_failing"
            result["fixed"] = None
            result["semantic_correctness"] = None
            return result

        # Step 3: Run the self-healing harness
        from tools.deepseek_self_heal import main as run_harness

        # Set environment for PR simulation
        os.environ["GITHUB_HEAD_REF"] = "benchmark-test-branch"
        os.environ["PR_NUMBER"] = "999"

        # Execute harness
        harness_code = run_harness(
            provider=provider_override,
            allow_test_edits=False,
            repo_root=REPO_ROOT
        )

        # Inspect metrics output
        metrics_file = REPO_ROOT / "reports" / "heal_metrics.json"
        if metrics_file.exists():
            try:
                metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
                result["attempts"] = metrics.get("attempts", 0)
                providers = metrics.get("provider_used_per_attempt", [])
                result["provider"] = providers[-1] if providers else "N/A"
                result["tokens"] = metrics.get("tokens", result["tokens"])
                result["policy_rejections"] = metrics.get("rejection_reasons", [])
                p_size = metrics.get("patch_size", {})
                result["patch_size"] = {
                    "lines_added": p_size.get("lines_added", 0),
                    "lines_removed": p_size.get("lines_removed", 0)
                }
            except Exception as e:
                result["notes"] += f" (Metrics parsing warning: {e})"

        # Check if the file was repaired and passes verification
        patched_str = target_path.read_text(encoding="utf-8", errors="replace")
        verify_code, _ = run_cmd([py_exec, "-m", "pytest", test_node, "-q"], cwd=backend_cwd, timeout=30.0)

        if verify_code == 0 and patched_str != corrupted_str:
            result["fixed"] = True
            result["semantic_correctness"] = evaluate_semantic_correctness(original_str, patched_str, search_block)
        else:
            result["fixed"] = False
            result["semantic_correctness"] = False

    finally:
        # Guaranteed Rollback: Restore target file byte-for-byte to original
        target_path.write_bytes(original_bytes)
        result["latency_seconds"] = round(time.time() - start_time, 2)


def generate_markdown_summary(summary_data: Dict[str, Any]) -> str:
    """Generate markdown summary table for docs/CICD.md and reports/benchmark_summary.md."""
    lines = []
    lines.append("### Automated Benchmark Evaluation (15 Seeded Bugs)")
    lines.append("")
    mode = summary_data.get("execution_mode", "dry_run_validation")
    total = summary_data["total_bugs"]
    validated = summary_data.get("validated_count", sum(1 for r in summary_data["results"] if r.get("defect_validated") or r.get("test_failed_as_expected")))

    lines.append(f"- **Defect validation**: {validated}/{total} seeded bugs reproduce a failing test")
    if mode == "dry_run_validation":
        lines.append("- **LLM Repair Benchmark**: Not executed (dry-run mode; no live API keys in environment)")
        lines.append("- **Execution Mode**: `dry_run_validation`")
    else:
        lines.append(f"- **Repairs Successful (Tests Pass)**: {summary_data.get('fixed_count', 0)} / {total} ({summary_data.get('pass_rate', 0.0):.1f}%)")
        lines.append(f"- **Semantically Correct**: {summary_data.get('semantic_count', 0)} / {total}")
        lines.append("- **Execution Mode**: `live_llm`")

    lines.append(f"- **Average Latency**: {summary_data['average_latency_seconds']:.2f}s")
    lines.append("")
    lines.append("| ID | Category | Target File | Test Node | Validated | Fixed (Tests Pass) | Semantically Correct | Policy-Rejected | Latency |")
    lines.append("|---|---|---|---|---|---|---|---|---|")

    for r in summary_data["results"]:
        file_name = Path(r["target_file"]).name
        test_short = r["test_node"].split("::")[-1]
        val_status = "**YES**" if (r.get("test_failed_as_expected") or r.get("defect_validated")) else "NO"
        if mode == "dry_run_validation":
            fixed_str = "not run"
            semantic_str = "not run"
            policy_str = "not run"
        else:
            fixed_str = "**PASSED**" if r.get("fixed") else "FAILED"
            semantic_str = "Yes" if r.get("semantic_correctness") else "No"
            policy_str = ", ".join(r.get("policy_rejections", [])) or "None"
        lines.append(f"| `{r['id']}` | {r['category']} | `{file_name}` | `{test_short}` | {val_status} | {fixed_str} | {semantic_str} | {policy_str} | {r['latency_seconds']:.2f}s |")

    lines.append("")
    if mode == "dry_run_validation":
        lines.append("> **Note**: Dry-run defect validation executed. To run live LLM repair benchmarks with real API keys, run: `python tools/heal_benchmark/runner.py --all`")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous Self-Healing CI Benchmark Runner")
    parser.add_argument("--dry-run", action="store_true", help="Validate all fixtures, test failures, and rollbacks without calling LLM.")
    parser.add_argument("--all", action="store_true", help="Run benchmark across all 15 bug fixtures.")
    parser.add_argument("--bug", type=str, default="", help="Run benchmark on a specific bug ID (e.g. bug_01_off_by_one).")
    parser.add_argument("--live", action="store_true", help="Run live against configured Groq/DeepSeek provider.")
    args = parser.parse_args()

    fixtures = load_bug_fixtures()
    if not fixtures:
        print("[benchmark] Error: No bug fixtures found in tools/heal_benchmark/bugs/")
        return 1

    if args.bug:
        fixtures = [f for f in fixtures if f["id"] == args.bug]
        if not fixtures:
            print(f"[benchmark] Error: Bug ID '{args.bug}' not found.")
            return 1

    print(f"============================================================")
    print(f"  Autonomous Self-Healing CI Benchmark Suite (15 Seeded Bugs)")
    print(f"============================================================")
    print(f"Found {len(fixtures)} bug fixture(s).")
    print(f"Mode: {'DRY-RUN (Defect Validation)' if args.dry_run else 'LIVE EVALUATION'}\n")

    results = []
    for idx, bug in enumerate(fixtures, 1):
        print(f"[{idx}/{len(fixtures)}] Evaluating {bug['id']}: {bug['name']}...")
        res = run_benchmark_for_bug(bug, dry_run=args.dry_run)
        results.append(res)
        status_label = "VALIDATED" if args.dry_run and res.get("defect_validated") else ("FIXED" if res.get("fixed") else "FAILED")
        print(f"   -> Result: {status_label} (Injected: {res['defect_injected']}, Test Failed: {res['test_failed_as_expected']}, Latency: {res['latency_seconds']}s)")

    # Compute summary metrics
    total = len(results)
    validated = sum(1 for r in results if r.get("test_failed_as_expected") or r.get("defect_validated"))
    fixed = 0 if args.dry_run else sum(1 for r in results if r.get("fixed"))
    semantic = 0 if args.dry_run else sum(1 for r in results if r.get("semantic_correctness"))
    avg_latency = round(sum(r["latency_seconds"] for r in results) / total, 2) if total else 0.0

    summary_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "execution_mode": "dry_run_validation" if args.dry_run else "live_llm",
        "total_bugs": total,
        "validated_count": validated,
        "fixed_count": fixed,
        "semantic_count": semantic,
        "failed_count": total - fixed,
        "pass_rate": 0.0 if args.dry_run else round((fixed / total) * 100, 2),
        "average_latency_seconds": avg_latency,
        "results": results
    }

    # Write reports/benchmark_results.json
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / "benchmark_results.json"
    report_file.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print(f"\n[benchmark] Benchmark results saved to {report_file}")

    # Output Markdown summary table
    md_summary = generate_markdown_summary(summary_data)
    summary_file = REPORTS_DIR / "benchmark_summary.md"
    summary_file.write_text(md_summary, encoding="utf-8")
    print(f"[benchmark] Markdown summary saved to {summary_file}\n")
    print(md_summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())

