import os
import json
from datetime import datetime
from upstash_redis import Redis

# Initialize Redis client for Vercel KV
redis = Redis(
    url=os.environ.get("KV_REST_API_URL", ""),
    token=os.environ.get("KV_REST_API_TOKEN", "")
)

def log_run(automation_name, status, message="", duration=0):
    if not os.environ.get("KV_REST_API_URL"):
        return

    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "name": automation_name,
        "status": status,
        "message": message[:1000],
        "duration": round(duration, 2)
    }
    
    redis.lpush(f"logs:{automation_name}", log_entry)
    redis.ltrim(f"logs:{automation_name}", 0, 49)
    redis.hset("automation:status", automation_name, log_entry)
    redis.lpush("activity_feed", log_entry)
    redis.ltrim("activity_feed", 0, 99)

# --- Dynamic Automation Management ---

def get_automations():
    """Returns a list of all dynamic automations."""
    ids = redis.smembers("automation_ids")
    if not ids:
        # Seed with defaults if empty
        defaults = [
            {"id": "apr26", "name": "APR 26 Performance", "script": "apr-26_performance.py", "sheet_id": "APR26_SHEET_ID", "destinations": "APR26_DESTINATIONS"},
            {"id": "overall", "name": "Overall Manish", "script": "overall_manish.py", "sheet_id": "OVERALL_SHEET_ID", "destinations": "OVERALL_DESTINATIONS"},
            {"id": "gew", "name": "GEW Whatsapp", "script": "gew_whatsapp.py", "sheet_id": "GEW_SHEET_ID", "destinations": "GEW_DESTINATIONS"},
            {"id": "new_biz", "name": "New Biz Cat", "script": "new_biz_cat_whatsapp.py", "sheet_id": "NEW_BIZ_SHEET_ID", "destinations": "NEW_BIZ_DESTINATIONS"}
        ]
        for item in defaults:
            save_automation(item)
        return defaults
    
    return [redis.hgetall(f"automation:{aid}") for aid in ids]

def save_automation(data):
    """Saves or updates an automation configuration."""
    aid = data["id"]
    redis.sadd("automation_ids", aid)
    redis.hset(f"automation:{aid}", data)

def delete_automation(aid):
    """Deletes an automation configuration."""
    name = redis.hget(f"automation:{aid}", "name")
    redis.srem("automation_ids", aid)
    redis.delete(f"automation:{aid}")
    if name:
        redis.delete(f"logs:{name}")
        redis.hdel("automation:status", name)
