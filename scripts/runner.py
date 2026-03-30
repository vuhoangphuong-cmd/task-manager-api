#!/usr/bin/env python3
import json
import subprocess
import sys
import re

BRIDGE = "python scripts/task_bridge.py"

def parse_input(text):
    # tìm ACTION
    match = re.search(r"ACTION:\s*(\w+)", text)
    if not match:
        raise ValueError("Không tìm thấy ACTION")

    action = match.group(1)

    # tìm JSON
    json_match = re.search(r"\{[\s\S]*\}", text)
    payload = {}

    if json_match:
        payload = json.loads(json_match.group(0))

    return action, payload


def run(action, payload):
    cmd = BRIDGE.split() + [action]

    if payload:
        p = subprocess.run(
            cmd,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
        )
    else:
        p = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
        )

    if p.returncode != 0:
        print("❌ Lỗi:", p.stderr or p.stdout)
    else:
        print("✅ Kết quả:")
        print(p.stdout)


def main():
    print("📥 Paste output từ OpenClaw (Ctrl+D để chạy):\n")
    text = sys.stdin.read()

    try:
        action, payload = parse_input(text)
        print(f"👉 ACTION: {action}")
        print(f"👉 PAYLOAD: {payload}\n")

        run(action, payload)

    except Exception as e:
        print("❌ Parse lỗi:", str(e))


if __name__ == "__main__":
    main()
