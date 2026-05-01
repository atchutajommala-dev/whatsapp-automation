import os
import time
from datetime import datetime
from upstash_redis import Redis

# Initialize Redis client for Vercel KV
redis = Redis(
    url=os.environ.get("KV_REST_API_URL", ""),
    token=os.environ.get("KV_REST_API_TOKEN", "")
)

def log_run(automation_name, status, message="", duration=0):
    """
    Logs an automation run to Vercel KV.
    """
    if not os.environ.get("KV_REST_API_URL"):
        print(f"Skipping KV logging for {automation_name}: KV_REST_API_URL not set")
        return

    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "name": automation_name,
        "status": status, # 'success' or 'error'
        "message": message[:1000], # Truncate long logs
        "duration": round(duration, 2)
    }
    
    # Store in a list for each automation
    redis.lpush(f"logs:{automation_name}", log_entry)
    # Keep only last 50 logs
    redis.ltrim(f"logs:{automation_name}", 0, 49)
    
    # Also update global last run status
    redis.hset("automation:status", automation_name, log_entry)
    
    # Add to global activity feed
    redis.lpush("activity_feed", log_entry)
    redis.ltrim("activity_feed", 0, 99)

def get_logs(automation_name):
    return redis.lrange(f"logs:{automation_name}", 0, -1)

def get_latest_statuses():
    return redis.hgetall("automation:status")

def get_activity_feed():
    return redis.lrange("activity_feed", 0, 19)
