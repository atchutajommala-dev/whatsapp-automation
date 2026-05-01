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
        "message": str(message)[:1000],
        "duration": round(duration, 2)
    }
    
    # Store as JSON string for consistency
    log_json = json.dumps(log_entry)
    
    redis.lpush(f"logs:{automation_name}", log_json)
    redis.ltrim(f"logs:{automation_name}", 0, 49)
    redis.hset("automation:status", automation_name, log_json)
    redis.lpush("activity_feed", log_json)
    redis.ltrim("activity_feed", 0, 99)

def get_automations():
    ids = redis.smembers("automation_ids")
    if not ids:
        # Default starting set
        defaults = [
            {"id": "apr26", "name": "APR 26 Performance", "script": "apr-26_performance.py", "sheet_id": "APR26_SHEET_ID", "destinations": "APR26_DESTINATIONS", "cron": "0 4 * * *"},
            {"id": "overall", "name": "Overall Manish", "script": "overall_manish.py", "sheet_id": "OVERALL_SHEET_ID", "destinations": "OVERALL_DESTINATIONS", "cron": "30 4 * * *"},
            {"id": "gew", "name": "GEW Whatsapp", "script": "gew_whatsapp.py", "sheet_id": "GEW_SHEET_ID", "destinations": "GEW_DESTINATIONS", "cron": "0 5 * * *"},
            {"id": "new_biz", "name": "New Biz Cat", "script": "new_biz_cat_whatsapp.py", "sheet_id": "NEW_BIZ_SHEET_ID", "destinations": "NEW_BIZ_DESTINATIONS", "cron": "0 5 * * *"}
        ]
        for item in defaults:
            save_automation(item)
        return defaults
    
    # Ensure we decode everything properly
    autos = []
    for aid in ids:
        raw = redis.hgetall(f"automation:{aid}")
        # Upstash might return dict with bytes or strings
        clean = {k: v for k, v in raw.items()}
        autos.append(clean)
    return autos

def save_automation(data):
    aid = data["id"]
    redis.sadd("automation_ids", aid)
    # Store all fields in the hash
    redis.hset(f"automation:{aid}", data)

def delete_automation(aid):
    name = redis.hget(f"automation:{aid}", "name")
    redis.srem("automation_ids", aid)
    redis.delete(f"automation:{aid}")
    if name:
        redis.delete(f"logs:{name}")
        redis.hdel("automation:status", name)
