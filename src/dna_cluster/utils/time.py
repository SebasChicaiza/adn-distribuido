import datetime

def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
