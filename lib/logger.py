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
    
    log_json = json.dumps(log_entry)
    redis.lpush(f"logs:{automation_name}", log_json)
    redis.ltrim(f"logs:{automation_name}", 0, 49)
    redis.hset("automation:status", automation_name, log_json)
    redis.lpush("activity_feed", log_json)
    redis.ltrim("activity_feed", 0, 99)

def get_automations():
    ids = redis.smembers("automation_ids")
    if not ids:
        # Re-seed with full configurations for the master script
        defaults = [
            {
                "id": "apr26", 
                "name": "APR 26 Performance", 
                "sheet_id": os.environ.get("APR26_SHEET_ID", "1S_5N..."), 
                "sheet_name": "Top Categories",
                "ranges": "A1:Q20",
                "destinations": os.environ.get("APR26_DESTINATIONS", "916303054457"), 
                "cron": "0 4 * * *"
            },
            {
                "id": "overall", 
                "name": "Overall Manish", 
                "sheet_id": os.environ.get("OVERALL_SHEET_ID", "1W_..."), 
                "sheet_name": "Whatsapp SS",
                "ranges": "A2:W17,A21:AA49,A53:W67,A71:W77",
                "destinations": os.environ.get("OVERALL_DESTINATIONS", "916303054457"), 
                "cron": "30 4 * * *"
            }
        ]
        for item in defaults:
            save_automation(item)
        return defaults
    
    autos = []
    for aid in ids:
        raw = redis.hgetall(f"automation:{aid}")
        autos.append(raw)
    return autos

def save_automation(data):
    aid = data["id"]
    redis.sadd("automation_ids", aid)
    redis.hset(f"automation:{aid}", data)

def delete_automation(aid):
    name = redis.hget(f"automation:{aid}", "name")
    redis.srem("automation_ids", aid)
    redis.delete(f"automation:{aid}")
    if name:
        redis.delete(f"logs:{name}")
        redis.hdel("automation:status", name)
