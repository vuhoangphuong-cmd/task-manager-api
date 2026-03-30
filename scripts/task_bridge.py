#!/usr/bin/env python3
import json
import sys
import requests

BASE = "http://127.0.0.1:8000/api/v1"

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "missing action"}))
        sys.exit(1)

    action = sys.argv[1]
    payload = {}
    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            payload = json.loads(raw)

    try:
        if action == "create_task":
            r = requests.post(f"{BASE}/tasks", json=payload, timeout=15)
        elif action == "list_tasks":
            r = requests.get(f"{BASE}/tasks", timeout=15)
        elif action == "update_progress":
            task_id = payload["task_id"]
            body = {
                "progress_percent": payload["progress_percent"],
                "comment": payload.get("comment"),
            }
            r = requests.post(f"{BASE}/tasks/{task_id}/progress", json=body, timeout=15)
        elif action == "dashboard_summary":
            r = requests.get(f"{BASE}/dashboard/summary", timeout=15)
        else:
            print(json.dumps({"success": False, "error": f"unknown action: {action}"}))
            sys.exit(1)

        print(json.dumps(r.json(), ensure_ascii=False))
        sys.exit(0 if r.ok else 1)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
import json
import sys
import requests

BASE = "http://127.0.0.1:8000/api/v1"

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "missing action"}))
        sys.exit(1)

    action = sys.argv[1]
    payload = {}

    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            payload = json.loads(raw)

    try:
        if action == "create_task":
            r = requests.post(f"{BASE}/tasks", json=payload, timeout=15)

        elif action == "list_tasks":
            r = requests.get(f"{BASE}/tasks", timeout=15)

        elif action == "update_progress":
            task_id = payload["task_id"]
            body = {
                "progress_percent": payload["progress_percent"],
                "comment": payload.get("comment")
            }
            r = requests.post(f"{BASE}/tasks/{task_id}/progress", json=body, timeout=15)

        elif action == "dashboard_summary":
            r = requests.get(f"{BASE}/dashboard/summary", timeout=15)

        else:
            print(json.dumps({"success": False, "error": f"unknown action: {action}"}, ensure_ascii=False))
            sys.exit(1)

        print(json.dumps(r.json(), ensure_ascii=False))
        sys.exit(0 if r.ok else 1)

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
