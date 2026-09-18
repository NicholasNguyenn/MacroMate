"""Risk spike: prove the MCP endpoint speaks Streamable HTTP correctly.

Retires risk 1 from docs/tech-stack-decision.md section 7 when run against a
deployed URL -- if a host buffers or mangles the stream, this fails here rather
than in week 4 against Alexa+.

Start the server, then:

    python scripts/spike_mcp_handshake.py                       # local
    python scripts/spike_mcp_handshake.py https://<app-runner>  # deployed
"""

from __future__ import annotations

import asyncio
import sys

from mcp import Client

REQUIRED_PROTOCOL = "2025-11-25"  # Alexa+ track floor


async def main(base_url: str) -> int:
    endpoint = base_url.rstrip("/") + "/mcp"
    print(f"connecting to {endpoint}")

    async with Client(endpoint) as client:
        info = client.server_info
        negotiated = client.protocol_version
        print(f"  server              : {info.name} v{info.version}")
        print(f"  negotiated protocol : {negotiated}")
        if str(negotiated) < REQUIRED_PROTOCOL:
            print(f"FAIL: negotiated {negotiated}, track requires >= {REQUIRED_PROTOCOL}")
            return 1

        tools = (await client.list_tools()).tools
        print(f"  tools               : {', '.join(t.name for t in tools)}")

        # The handoff's worked example, end to end over the wire.
        result = await client.call_tool(
            "calculate_portions",
            {"total_calories": 1800, "total_protein_g": 150, "portions": 4},
        )
        payload = result.structured_content or {}
        print(f"  calculate_portions  : {payload}")

        calories = payload.get("calories_per_portion")
        protein = payload.get("protein_g_per_portion")
        if (calories, protein) != (450, 37.5):
            print(f"FAIL: expected 450 kcal / 37.5 g, got {calories} / {protein}")
            return 1

    print("OK: handshake, tool listing, and round-trip calculation all succeeded")
    return 0


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
    raise SystemExit(asyncio.run(main(url)))
