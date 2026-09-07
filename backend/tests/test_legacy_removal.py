import os
import re
from pathlib import Path

# Files/directories to ignore during repo grep
IGNORED_DIRS = {".git", ".venv", "venv", "env", "node_modules", "dist", "build", "__pycache__", ".pytest_cache", "brain", ".benchmarks", "screenshots"}


def test_legacy_removal_zero_references():
    """
    Asserts zero remaining occurrences of legacy concepts across the codebase:
    - CompetitorPrice
    - Crawl4AI
    - pconfigs
    - _get_multi_platform_fallback
    """
    repo_root = Path(__file__).resolve().parents[2]

    # Split targets to avoid self-match in test file
    targets = [
        "Competitor" + "Price",
        "Crawl" + "4AI",
        "pcon" + "figs",
        "_get_multi_platform_" + "fallback",
    ]

    violations = []

    for root, dirs, files in os.walk(repo_root):
        # Exclude ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for file in files:
            file_path = Path(root) / file
            if file == "test_legacy_removal.py":
                continue
            # Only check source and config files
            if file_path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".html"}:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for target in targets:
                        if target in content:
                            violations.append(f"{file_path}: contains '{target}'")
                except Exception:
                    pass

    assert len(violations) == 0, f"Found legacy references:\n" + "\n".join(violations)
