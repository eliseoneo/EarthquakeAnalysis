#!/usr/bin/env python3
"""UI standalone — Capa C H04."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from layer_c.ui import mount_layer_c_panel


def build_ui():
    import gradio as gr

    with gr.Blocks(title="Capa C — Analisis H04 del evento") as demo:
        mount_layer_c_panel(gr)
    return demo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7863)
    args = parser.parse_args()
    build_ui().launch(server_name=args.host, server_port=args.port)


if __name__ == "__main__":
    main()