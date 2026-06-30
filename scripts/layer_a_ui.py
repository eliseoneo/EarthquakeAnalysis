#!/usr/bin/env python3
"""UI Gradio — Capa A: Tectónica Principal (sección aislada)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from layer_a.ui import mount_layer_a_panel


def build_ui():
    import gradio as gr

    with gr.Blocks(title="Capa A — Tectónica Principal") as demo:
        mount_layer_a_panel(gr)
    return demo


def main() -> None:
    parser = argparse.ArgumentParser(description="UI Capa A — Tectónica Principal")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7861)
    args = parser.parse_args()

    demo = build_ui()
    demo.launch(server_name=args.host, server_port=args.port)


if __name__ == "__main__":
    main()
