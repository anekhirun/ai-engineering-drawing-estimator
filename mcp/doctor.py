from __future__ import annotations

import json

import cv2
import fitz
import numpy
from PIL import Image

from server import VERSION, handle


def main() -> None:
    initialized = handle({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18"},
    })
    tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tool_names = [item["name"] for item in tools["result"]["tools"]]
    if len(tool_names) != 6:
        raise RuntimeError(f"Expected 6 MCP tools, found {len(tool_names)}")
    report = {
        "status": "ok",
        "version": VERSION,
        "protocol": initialized["result"]["protocolVersion"],
        "tools": tool_names,
        "dependencies": {
            "opencv": cv2.__version__,
            "pymupdf": fitz.__version__,
            "numpy": numpy.__version__,
            "pillow": Image.__version__,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
