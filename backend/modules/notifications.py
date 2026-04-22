import subprocess
import json


WATCHED_APPS = {
    "com.whatsapp": "WhatsApp",
    "com.facebook.orca": "Messenger",
    "org.telegram.messenger": "Telegram",
    "com.google.android.gm": "Gmail",
}


def _run_termux_command(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def get_battery_level() -> str:
    output = _run_termux_command(["termux-battery-status"])
    if not output:
        return "Battery level unavailable."
    try:
        data = json.loads(output)
        level = data.get("percentage", "?")
        status = data.get("status", "").lower()
        if status == "charging":
            return f"Battery at {level}%, charging."
        return f"Battery at {level}%."
    except Exception:
        return "Battery level unavailable."


def get_notification_summary() -> str:
    output = _run_termux_command(["termux-notification-list"])
    if not output:
        return "No notifications available."

    try:
        notifications = json.loads(output)
    except Exception:
        return "Could not read notifications."

    messages = []
    for notif in notifications:
        pkg = notif.get("packageName", "")
        app_name = WATCHED_APPS.get(pkg)
        if not app_name:
            continue

        title = notif.get("title", "").strip()
        content = notif.get("content", "").strip()
        text = notif.get("text", "").strip()

        body = content or text
        if not body:
            continue

        # Skip bundled summary notifications like "5 messages"
        if body.isdigit() or "messages" in body.lower() and len(body) < 20:
            continue

        sender = title if title else app_name
        messages.append(f"From {sender}: '{body}'")

    if not messages:
        return "No new messages."

    count = len(messages)
    summary = f"You have {count} new {'message' if count == 1 else 'messages'}. "
    summary += " ".join(messages[:3])  # read up to 3 aloud
    if count > 3:
        summary += f" And {count - 3} more."
    return summary
