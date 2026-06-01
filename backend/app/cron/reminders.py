from datetime import UTC, datetime
from typing import Any


async def fire_due_reminders(
    db: Any,
    *,
    user_id: str,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(UTC)
    cursor = db.reminders.find(
        {
            "user_id": user_id,
            "status": "pending",
            "fires_at": {"$lte": now},
        }
    ).sort("fires_at", 1)

    fired = 0
    message_ids: list[str] = []
    async for reminder in cursor:
        reminder_id = str(reminder["_id"])
        existing = await db.inbox_messages.find_one(
            {
                "user_id": user_id,
                "type": "reminder",
                "metadata.reminder_id": reminder_id,
            }
        )
        if existing:
            await db.reminders.update_one(
                {"_id": reminder["_id"], "status": "pending"},
                {"$set": {"status": "fired", "fired_at": now}},
            )
            continue

        result = await db.inbox_messages.insert_one(
            {
                "user_id": user_id,
                "type": "reminder",
                "title": "Reminder",
                "body": reminder["text"],
                "status": "unread",
                "created_at": now,
                "read_at": None,
                "metadata": {
                    "reminder_id": reminder_id,
                    "source": "reminder_cron",
                    "scheduled_source": reminder.get("source"),
                },
            }
        )
        await db.reminders.update_one(
            {"_id": reminder["_id"], "status": "pending"},
            {"$set": {"status": "fired", "fired_at": now}},
        )
        fired += 1
        message_ids.append(str(result.inserted_id))

    return {"fired": fired, "message_ids": message_ids}
