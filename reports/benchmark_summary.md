### Automated Benchmark Evaluation (15 Seeded Bugs)

- **Defect validation**: 15/15 seeded bugs reproduce a failing test
- **LLM Repair Benchmark**: Not executed (dry-run mode; no live API keys in environment)
- **Execution Mode**: `dry_run_validation`
- **Average Latency**: 6.49s

| ID | Category | Target File | Test Node | Validated | Fixed (Tests Pass) | Semantically Correct | Policy-Rejected | Latency |
|---|---|---|---|---|---|---|---|---|
| `bug_01_off_by_one` | off_by_one | `security_guardrails.py` | `test_check_sanity_bound` | **YES** | not run | not run | not run | 6.12s |
| `bug_02_wrong_operator` | wrong_operator | `security_guardrails.py` | `test_canonical_margin_floor_units` | **YES** | not run | not run | not run | 6.25s |
| `bug_03_missing_null_check` | missing_null_check | `security_guardrails.py` | `test_sanitize_for_prompt` | **YES** | not run | not run | not run | 6.32s |
| `bug_04_wrong_default` | wrong_default | `security_guardrails.py` | `test_effective_min_margin_pct` | **YES** | not run | not run | not run | 6.35s |
| `bug_05_bad_import_name` | bad_import_name | `price_writer.py` | `test_below_floor_rejection` | **YES** | not run | not run | not run | 5.31s |
| `bug_06_swapped_arguments` | swapped_arguments | `price_writer.py` | `test_sanity_bound_rejection_and_flagging` | **YES** | not run | not run | not run | 6.21s |
| `bug_07_incorrect_rounding` | incorrect_rounding | `price_writer.py` | `test_sanity_override_success` | **YES** | not run | not run | not run | 6.96s |
| `bug_08_wrong_comparison` | wrong_comparison_direction | `price_writer.py` | `test_below_floor_rejection` | **YES** | not run | not run | not run | 6.75s |
| `bug_09_inverted_boolean` | inverted_boolean | `circuit_breaker.py` | `test_parse_and_no_match_errors_do_not_trip_circuit` | **YES** | not run | not run | not run | 7.33s |
| `bug_10_wrong_multiplier` | wrong_operator | `circuit_breaker.py` | `test_circuit_breaker_exponential_backoff_and_half_open` | **YES** | not run | not run | not run | 7.01s |
| `bug_11_missing_dict_fallback` | missing_dict_fallback | `marketplace_normalizer.py` | `test_marketplace_normalizer_standardizes_results` | **YES** | not run | not run | not run | 6.95s |
| `bug_12_broken_regex` | broken_regex | `marketplace_normalizer.py` | `test_marketplace_normalizer_standardizes_results` | **YES** | not run | not run | not run | 6.44s |
| `bug_13_ambiguous_tolerance` | hard_ambiguous | `price_writer.py` | `test_stale_price_optimistic_concurrency` | **YES** | not run | not run | not run | 6.69s |
| `bug_14_inverted_set_logic` | hard_ambiguous | `security_guardrails.py` | `test_assert_no_client_supplied_org_id` | **YES** | not run | not run | not run | 6.22s |
| `bug_15_decay_window_logic` | hard_ambiguous | `circuit_breaker.py` | `test_sliding_window_failure_decay_after_60_minutes` | **YES** | not run | not run | not run | 6.45s |

> **Note**: Dry-run defect validation executed. To run live LLM repair benchmarks with real API keys, run: `python tools/heal_benchmark/runner.py --all`