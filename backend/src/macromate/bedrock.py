"""Thin Amazon Bedrock client for the conversational layer.

The model interprets requests and drives conversation. It does not calculate --
nutrition math lives in `macromate.nutrition` (AGENTS.md invariant 2).
"""

from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import ClientError

from macromate.config import settings


class BedrockUnavailable(RuntimeError):
    """Bedrock could not be reached, or the model is not enabled for this account."""


def get_client(region: str | None = None) -> Any:
    return boto3.client("bedrock-runtime", region_name=region)


def converse(
    messages: list[dict[str, Any]],
    *,
    system: str | None = None,
    model_id: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """Send a turn to Bedrock via the Converse API and return the text reply."""
    client = get_client()
    kwargs: dict[str, Any] = {
        "modelId": model_id or settings.bedrock_model_id,
        "messages": messages,
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if system:
        kwargs["system"] = [{"text": system}]

    try:
        response = client.converse(**kwargs)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        if code in {"AccessDeniedException", "ValidationException"}:
            raise BedrockUnavailable(
                f"Bedrock rejected the request ({code}). Claude on Bedrock requires "
                "per-account, per-region model enablement -- check model access in "
                "the Bedrock console for this region."
            ) from exc
        raise

    return response["output"]["message"]["content"][0]["text"]
