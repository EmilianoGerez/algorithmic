import redis

def get_redis_connection() -> redis.Redis:
    return redis.Redis(host="localhost", port=6379, decode_responses=True)
