import sys

from redis import Redis
from rq import Connection, Queue, Worker


def main() -> None:
    listen = ["default"]
    redis_url = sys.argv[1] if len(sys.argv) > 1 else "redis://localhost:6379"
    conn = Redis.from_url(redis_url)
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()


if __name__ == "__main__":
    main()
