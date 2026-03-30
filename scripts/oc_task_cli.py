#!/usr/bin/env python3
import argparse
import json
import requests
import sys
import os

BASE = "http://127.0.0.1:8000/api/v1"
ACTOR_FILE = os.path.expanduser("~/.openclaw/actor.env")

def set_actor(actor_id: str):
    os.makedirs(os.path.dirname(ACTOR_FILE), exist_ok=True)
    with open(ACTOR_FILE, "w") as f:
        f.write(f"TASK_ACTOR_ID={actor_id}\n")

def get_actor_file():
    if os.path.exists(ACTOR_FILE):
        with open(ACTOR_FILE) as f:
            for line in f:
                if line.startswith("TASK_ACTOR_ID="):
                    return line.strip().split("=")[1]
    return None

def get_actor():
    actor = get_actor_file()
    if not actor:
        print(json.dumps({"success": False, "error": "No actor set. Use switch-user first"}))
        sys.exit(1)
    return actor

def pp(resp):
    try:
        print(json.dumps(resp.json(), ensure_ascii=False))
    except Exception:
        print(resp.text)

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ===== BASIC =====
    sub.add_parser("dashboard")
    sub.add_parser("my-dashboard")
    sub.add_parser("my-work")
    sub.add_parser("list")
    sub.add_parser("whoami")

    # ===== SWITCH USER =====
    p_switch = sub.add_parser("switch-user")
    p_switch.add_argument("--user-id", required=True)

    # ===== DETAIL =====
    p_detail = sub.add_parser("detail")
    p_detail.add_argument("--task-id", required=True)

    # ===== CREATE =====
    p_create = sub.add_parser("create")
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--description", default="")
    p_create.add_argument("--priority", default="medium")
    p_create.add_argument("--due-at", required=True)
    p_create.add_argument("--owner-user-id", required=True)
    p_create.add_argument("--reviewer-user-id", required=True)

    # ===== PROGRESS =====
    p_update = sub.add_parser("progress")
    p_update.add_argument("--task-id", required=True)
    p_update.add_argument("--progress", type=int, required=True)
    p_update.add_argument("--comment", default="")

    # ===== SUBMIT =====
    p_submit = sub.add_parser("submit")
    p_submit.add_argument("--task-id", required=True)
    p_submit.add_argument("--result-summary", default="")
    p_submit.add_argument("--comment", default="")

    # ===== REVIEW =====
    p_review = sub.add_parser("review")
    p_review.add_argument("--task-id", required=True)
    p_review.add_argument("--decision", required=True)
    p_review.add_argument("--review-note", default="")

    args = parser.parse_args()

    try:
        # ===== WHOAMI =====
        if args.cmd == "whoami":
            actor = get_actor_file()
            print(json.dumps({"success": True, "actor": actor}))
            sys.exit(0)

        # ===== SWITCH USER =====
        if args.cmd == "switch-user":
            set_actor(args.user_id)
            print(json.dumps({"success": True, "actor": args.user_id}))
            sys.exit(0)

        # ===== DASHBOARD =====
        if args.cmd == "dashboard":
            r = requests.get(f"{BASE}/dashboard/summary", timeout=20)
            pp(r)
            sys.exit(0 if r.ok else 1)

        if args.cmd == "my-dashboard":
            actor = get_actor()
            r = requests.get(f"{BASE}/dashboard/summary-by-user/{actor}", timeout=20)
            pp(r)
            sys.exit(0 if r.ok else 1)

        if args.cmd == "my-work":
            actor = get_actor()
            r = requests.get(f"{BASE}/dashboard/my-work/{actor}", timeout=20)
            pp(r)
            sys.exit(0 if r.ok else 1)

        # ===== LIST =====
        if args.cmd == "list":
            r = requests.get(f"{BASE}/tasks", timeout=20)
            pp(r)
            sys.exit(0 if r.ok else 1)

        # ===== DETAIL =====
        if args.cmd == "detail":
            r = requests.get(f"{BASE}/tasks/{args.task_id}", timeout=20)
            pp(r)
            sys.exit(0 if r.ok else 1)

        # ===== CREATE =====
        if args.cmd == "create":
            actor = get_actor()
            payload = {
                "title": args.title,
                "description": args.description,
                "creator_user_id": actor,
                "owner_user_id": args.owner_user_id,
                "reviewer_user_id": args.reviewer_user_id,
                "priority": args.priority,
                "due_at": args.due_at,
            }
            r = requests.post(f"{BASE}/tasks", json=payload, timeout=20)
            pp(r)
            sys.exit(0 if r.ok else 1)

        # ===== PROGRESS =====
        if args.cmd == "progress":
            actor = get_actor()
            payload = {
                "actor_user_id": actor,
                "progress_percent": args.progress,
                "comment": args.comment,
            }
            r = requests.post(f"{BASE}/tasks/{args.task_id}/progress", json=payload, timeout=20)
            pp(r)
            sys.exit(0 if r.ok else 1)

        # ===== SUBMIT =====
        if args.cmd == "submit":
            actor = get_actor()
            payload = {
                "actor_user_id": actor,
                "result_summary": args.result_summary,
                "comment": args.comment,
            }
            r = requests.post(f"{BASE}/tasks/{args.task_id}/submit", json=payload, timeout=20)
            pp(r)
            sys.exit(0 if r.ok else 1)

        # ===== REVIEW =====
        if args.cmd == "review":
            actor = get_actor()
            payload = {
                "actor_user_id": actor,
                "decision": args.decision,
                "review_note": args.review_note,
            }
            r = requests.post(f"{BASE}/tasks/{args.task_id}/review", json=payload, timeout=20)
            pp(r)
            sys.exit(0 if r.ok else 1)

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
