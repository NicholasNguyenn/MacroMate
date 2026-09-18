"""Risk spike: confirm Claude on Bedrock is enabled for this account and region.

Retires risk 3 from docs/tech-stack-decision.md section 7. Model access is
granted per-account and per-region and is not instant, so run this on day 1 --
before Bedrock is on the critical path.

    python scripts/spike_bedrock.py
"""

from __future__ import annotations

from macromate.bedrock import BedrockUnavailable, converse
from macromate.config import settings


def main() -> int:
    print(f"model: {settings.bedrock_model_id}")
    try:
        reply = converse(
            [{"role": "user", "content": [{"text": "Reply with exactly: BEDROCK OK"}]}],
            max_tokens=16,
        )
    except BedrockUnavailable as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 - spike script; surface anything
        print(f"FAIL: {type(exc).__name__}: {exc}")
        print("If this is a credentials error, configure the AWS CLI or set AWS_PROFILE.")
        return 1

    print(f"reply: {reply.strip()}")
    print("OK: Bedrock reachable and model enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
