import os
import sys

from redis import Redis
from rq import Queue, Worker

_FAKE_REDIS_SERVER = None


def main() -> None:
    listen = ["default"]
    redis_url = os.environ.get(
        "REDIS_URL", sys.argv[1] if len(sys.argv) > 1 else "redis://localhost:6379"
    )

    if os.environ.get("USE_FAKEREDIS") == "1":
        print("Worker: Using FakeRedis for local testing.")
        from fakeredis import FakeServer, FakeStrictRedis

        global _FAKE_REDIS_SERVER
        if _FAKE_REDIS_SERVER is None:
            _FAKE_REDIS_SERVER = FakeServer()
        conn = FakeStrictRedis(server=_FAKE_REDIS_SERVER)
    else:
        print(f"Worker: Connecting to Redis at {redis_url}")
        conn = Redis.from_url(redis_url)

    queues = [Queue(name, connection=conn) for name in listen]
    worker = Worker(queues, connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
