import sys

from redis import Redis
from rq import Queue, Worker


def main() -> None:
    listen = ["default"]
    redis_url = sys.argv[1] if len(sys.argv) > 1 else "redis://localhost:6379"
    conn = Redis.from_url(redis_url)
    queues = [Queue(name, connection=conn) for name in listen]
    worker = Worker(queues, connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
