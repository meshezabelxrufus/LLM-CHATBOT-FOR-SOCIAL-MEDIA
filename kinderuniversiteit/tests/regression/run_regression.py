"""
Kinderuniversiteit AI Receptionist — Regression Test Runner
============================================================

Executes every test case in tests/regression/test_cases.py against the
live FastAPI backend and prints a colour-coded PASS / FAIL table with a
summary at the end.

Usage
-----
    # From the project root (kinderuniversiteit/)
    python tests/regression/run_regression.py

    # Target a different host
    python tests/regression/run_regression.py --base-url http://staging.example.com

    # Run only a specific category
    python tests/regression/run_regression.py --category PAYMENT_STATUS

    # Run only specific test IDs (comma-separated)
    python tests/regression/run_regression.py --ids PAY-STATUS-001,BANK-001

    # Save a JSON report
    python tests/regression/run_regression.py --report regression_report.json

    # Verbose mode — print full reply text for every test
    python tests/regression/run_regression.py --verbose

    # Fail fast — stop at first failure
    python tests/regression/run_regression.py --fail-fast

Environment
-----------
    BASE_URL         Override the target host (default: http://localhost:8000)
    REQUEST_TIMEOUT  Per-request timeout in seconds (default: 60)
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

# ── make sure the project root is on sys.path ─────────────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tests.regression.test_cases import TEST_CASES, TestCase  # noqa: E402

# ── ANSI colour codes ─────────────────────────────────────────────────────────
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"
_DIM    = "\033[2m"


def _c(text: str, colour: str) -> str:
    """Wrap text in ANSI colour if stdout is a tty."""
    if sys.stdout.isatty():
        return f"{colour}{text}{_RESET}"
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    test_id: str
    category: str
    description: str
    endpoint: str
    passed: bool
    http_status: int
    duration_ms: float
    reply_text: str
    failures: list[str]
    skipped: bool = False
    skip_reason: str = ""
    raw_response: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────────────
# API client helpers
# ─────────────────────────────────────────────────────────────────────────────

def call_demo(client: httpx.Client, base_url: str, tc: TestCase) -> tuple[int, dict]:
    payload = {"message": tc.message, "history": tc.history}
    r = client.post(f"{base_url}/api/v1/demo/chat", json=payload)
    return r.status_code, r.json() if r.content else {}


def _sign_payload(body_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 of the raw body using the webhook secret.

    Returns a bare hex digest (no 'sha256=' prefix) matching the format
    the backend's verify_signature() function accepts.
    """
    return hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()


def call_webhook(
    client: httpx.Client,
    base_url: str,
    tc: TestCase,
    webhook_secret: str = "",
) -> tuple[int, dict]:
    """
    POST to /api/v1/webhook/manychat.

    When webhook_secret is supplied (read from .env or --webhook-secret flag)
    we compute and attach a valid HMAC-SHA256 signature so the backend's auth
    layer passes and we reach payload validation.  This lets us properly test
    400-level payload errors.

    If no secret is configured (local dev with MANYCHAT_WEBHOOK_SECRET unset)
    the backend skips verification and we send an empty header.
    """
    body_bytes = json.dumps(tc.webhook_payload, separators=(",", ":")).encode()

    if webhook_secret:
        sig = _sign_payload(body_bytes, webhook_secret)
    else:
        sig = ""

    r = client.post(
        f"{base_url}/api/v1/webhook/manychat",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "x-manychat-signature": sig,
        },
    )
    return r.status_code, r.json() if r.content else {}


def call_health(client: httpx.Client, base_url: str) -> tuple[int, dict]:
    r = client.get(f"{base_url}/api/v1/health")
    return r.status_code, r.json() if r.content else {}


# ─────────────────────────────────────────────────────────────────────────────
# Assertion engine
# ─────────────────────────────────────────────────────────────────────────────

def _extract_reply(endpoint: str, data: dict) -> str:
    """Pull the human-readable reply out of the response body."""
    if endpoint == "demo":
        return str(data.get("reply", ""))
    if endpoint == "webhook":
        try:
            return data["content"]["messages"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return str(data)
    # health / other
    return str(data)


def _detect_language(text: str) -> str:
    """Very lightweight Dutch vs English heuristic for reply validation."""
    nl_markers = ["de ", "het ", "een ", "zijn ", "voor ", "van ", "met ",
                  "dat ", "dit ", "ook ", "ons ", "uw ", "je ", "jij "]
    en_markers = ["the ", "and ", "for ", "our ", "your ", "you ", "are ",
                  "this ", "that ", "with ", "will ", "can "]
    text_lower = text.lower()
    nl_score = sum(text_lower.count(m) for m in nl_markers)
    en_score = sum(text_lower.count(m) for m in en_markers)
    if nl_score == 0 and en_score == 0:
        return "unknown"
    return "nl" if nl_score >= en_score else "en"


def run_assertions(tc: TestCase, http_status: int, data: dict, reply: str) -> list[str]:
    """Return a list of failure messages.  Empty list == PASS."""
    failures: list[str] = []

    # ── HTTP status ───────────────────────────────────────────────────────────
    if http_status != tc.expected_http_status:
        failures.append(
            f"HTTP status: expected {tc.expected_http_status}, got {http_status}"
        )
        # If status is wrong there's nothing useful to check further
        if http_status >= 400:
            return failures

    # ── Minimum reply length ──────────────────────────────────────────────────
    if len(reply) < tc.min_reply_length:
        failures.append(
            f"Reply too short: {len(reply)} chars (minimum {tc.min_reply_length})"
        )

    # ── Required keywords (at least one must match) ───────────────────────────
    if tc.contains_keywords:
        reply_lower = reply.lower()
        matched = any(kw.lower() in reply_lower for kw in tc.contains_keywords)
        if not matched:
            failures.append(
                f"No required keyword found. Expected one of: {tc.contains_keywords}"
            )

    # ── Excluded keywords (none must appear) ──────────────────────────────────
    if tc.excludes_keywords:
        reply_lower = reply.lower()
        for kw in tc.excludes_keywords:
            if kw.lower() in reply_lower:
                failures.append(f"Forbidden keyword found in reply: '{kw}'")

    # ── Escalation expectation ────────────────────────────────────────────────
    if tc.expect_escalation:
        # For the demo endpoint: the [ESCALATE] block is stripped,
        # so we check for typical human-handoff phrasing instead.
        escalation_phrases = [
            "team", "medewerker", "colleague", "contact",
            "human", "agent", "doorverbinden", "verify",
            "controleert", "opneemt",
        ]
        reply_lower = reply.lower()
        if not any(p in reply_lower for p in escalation_phrases):
            failures.append(
                "Expected escalation language (team/medewerker/colleague/verify...) "
                "but none found in reply"
            )

    # ── Language expectation ──────────────────────────────────────────────────
    if tc.expected_language not in ("any", "unknown"):
        detected = _detect_language(reply)
        if detected != "unknown" and detected != tc.expected_language:
            failures.append(
                f"Language mismatch: expected '{tc.expected_language}', "
                f"detected '{detected}'"
            )

    # ── Webhook-specific: verify ManyChat envelope shape ─────────────────────
    if tc.endpoint == "webhook" and http_status == 200:
        if "version" not in data or data.get("version") != "v2":
            failures.append("Webhook response missing 'version: v2' envelope")
        if "content" not in data:
            failures.append("Webhook response missing 'content' key")

    return failures


# ─────────────────────────────────────────────────────────────────────────────
# Core runner
# ─────────────────────────────────────────────────────────────────────────────

def run_test(
    tc: TestCase,
    client: httpx.Client,
    base_url: str,
    verbose: bool = False,
    webhook_secret: str = "",
) -> TestResult:
    start = time.perf_counter()
    http_status = 0
    data: dict = {}
    reply = ""
    failures: list[str] = []

    try:
        if tc.endpoint == "demo":
            http_status, data = call_demo(client, base_url, tc)
        elif tc.endpoint == "webhook":
            http_status, data = call_webhook(client, base_url, tc, webhook_secret)
        elif tc.endpoint == "health":
            http_status, data = call_health(client, base_url)
        else:
            return TestResult(
                test_id=tc.id, category=tc.category, description=tc.description,
                endpoint=tc.endpoint, passed=False, http_status=0,
                duration_ms=0, reply_text="", raw_response=None,
                failures=[f"Unknown endpoint: {tc.endpoint}"],
            )

        reply = _extract_reply(tc.endpoint, data)
        failures = run_assertions(tc, http_status, data, reply)

    except httpx.TimeoutException:
        failures = [f"Request timed out after {client.timeout.read}s"]
    except Exception as exc:
        failures = [f"Unexpected exception: {type(exc).__name__}: {exc}"]

    duration_ms = (time.perf_counter() - start) * 1000

    return TestResult(
        test_id=tc.id,
        category=tc.category,
        description=tc.description,
        endpoint=tc.endpoint,
        passed=len(failures) == 0,
        http_status=http_status,
        duration_ms=duration_ms,
        reply_text=reply,
        failures=failures,
        raw_response=data,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reporting helpers
# ─────────────────────────────────────────────────────────────────────────────

def _print_result(res: TestResult, verbose: bool) -> None:
    status_str = _c("PASS", _GREEN) if res.passed else _c("FAIL", _RED)
    print(
        f"  {status_str}  {_c(res.test_id, _BOLD):<20}  "
        f"{_c(res.category, _CYAN):<20}  "
        f"{res.http_status}  {res.duration_ms:>7.0f}ms  "
        f"{res.description}"
    )
    if not res.passed:
        for f in res.failures:
            print(f"         {_c('✗ ' + f, _RED)}")
    if verbose and res.reply_text:
        # Truncate very long replies for readability
        preview = res.reply_text[:300] + ("…" if len(res.reply_text) > 300 else "")
        print(f"         {_c('Reply: ' + preview, _DIM)}")


def _print_summary(results: list[TestResult], total_ms: float) -> None:
    passed  = sum(1 for r in results if r.passed)
    failed  = sum(1 for r in results if not r.passed)
    skipped = sum(1 for r in results if r.skipped)
    total   = len(results)

    print()
    print("─" * 80)
    print(_c(f"  RESULTS  {passed}/{total} passed", _BOLD))
    print(f"  Passed : {_c(str(passed), _GREEN)}")
    print(f"  Failed : {_c(str(failed), _RED)}")
    if skipped:
        print(f"  Skipped: {_c(str(skipped), _YELLOW)}")
    print(f"  Total time: {total_ms:.0f}ms  ({total_ms/1000:.1f}s)")
    print("─" * 80)

    if failed > 0:
        print()
        print(_c("  Failed tests:", _RED + _BOLD))
        for r in results:
            if not r.passed:
                print(f"    {r.test_id}  {r.description}")
                for f in r.failures:
                    print(f"      • {f}")
        print()


def _save_report(results: list[TestResult], path: str) -> None:
    report = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "skipped": sum(1 for r in results if r.skipped),
        },
        "results": [
            {
                "id": r.test_id,
                "category": r.category,
                "description": r.description,
                "endpoint": r.endpoint,
                "passed": r.passed,
                "http_status": r.http_status,
                "duration_ms": round(r.duration_ms, 1),
                "failures": r.failures,
                "reply_preview": r.reply_text[:200],
            }
            for r in results
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print(f"\n  Report saved → {path}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _load_dotenv_secret() -> str:
    """Read MANYCHAT_WEBHOOK_SECRET from the project .env file as a fallback.

    This lets the runner work out-of-the-box without requiring the user to
    set the env var manually — useful for local development.
    """
    env_path = os.path.join(_ROOT, ".env")
    if not os.path.exists(env_path):
        return ""
    with open(env_path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("MANYCHAT_WEBHOOK_SECRET="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                # Ignore placeholder values
                if value and value not in ("test-placeholder", "placeholder", ""):
                    return value
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kinderuniversiteit AI Receptionist Regression Runner"
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "http://localhost:8000"),
        help="Base URL of the FastAPI backend (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("REQUEST_TIMEOUT", "60")),
        help="Per-request timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--webhook-secret",
        default=os.getenv("WEBHOOK_SECRET", ""),
        help="ManyChat webhook HMAC secret (auto-read from .env if not set)",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Run only tests in this category (e.g. PAYMENT_STATUS)",
    )
    parser.add_argument(
        "--ids",
        default=None,
        help="Run only these test IDs, comma-separated (e.g. PAY-STATUS-001,BANK-001)",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Path to write a JSON report file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print reply text for every test",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately on the first failure",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # ── Resolve webhook secret ────────────────────────────────────────────────
    # Priority: --webhook-secret flag > WEBHOOK_SECRET env var > .env file
    webhook_secret = args.webhook_secret or _load_dotenv_secret()

    # ── Filter test cases ─────────────────────────────────────────────────────
    cases = list(TEST_CASES)
    if args.category:
        cases = [tc for tc in cases if tc.category == args.category.upper()]
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        cases = [tc for tc in cases if tc.id in wanted]

    if not cases:
        print(_c("No test cases matched the filter.", _YELLOW))
        return 0

    sig_status = _c(f"signing ({webhook_secret[:4]}…)", _GREEN) if webhook_secret else _c("none (sig check skipped in dev)", _YELLOW)

    print()
    print(_c("  Kinderuniversiteit AI Receptionist — Regression Suite", _BOLD))
    print(f"  Target     : {args.base_url}")
    print(f"  Cases      : {len(cases)}")
    print(f"  Timeout    : {args.timeout}s")
    print(f"  HMAC sig   : {sig_status}")
    print(f"  Started    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print(
        f"  {'STATUS':<6}  {'ID':<20}  {'CATEGORY':<20}  "
        f"{'HTTP'}  {'DURATION':>10}  DESCRIPTION"
    )
    print("─" * 100)

    results: list[TestResult] = []

    with httpx.Client(timeout=args.timeout) as client:
        suite_start = time.perf_counter()

        for tc in cases:
            res = run_test(
                tc, client, args.base_url,
                verbose=args.verbose,
                webhook_secret=webhook_secret,
            )
            results.append(res)
            _print_result(res, verbose=args.verbose)

            if args.fail_fast and not res.passed:
                print(_c("\n  FAIL FAST: stopping at first failure.", _RED))
                break

        total_ms = (time.perf_counter() - suite_start) * 1000

    _print_summary(results, total_ms)

    if args.report:
        _save_report(results, args.report)

    # Exit code: 0 = all passed, 1 = failures
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
