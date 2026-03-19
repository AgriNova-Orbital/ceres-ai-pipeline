# Logging System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** To implement a robust and scalable logging system for the project.

**Architecture:** We will use Python's built-in `logging` module with a JSON formatter. Logs will be sent to standard output and collected by a Vector logging agent running in a Docker container. Vector will be configured to parse the JSON logs and can be extended to send them to various sinks.

**Tech Stack:**
- Python `logging` module
- `python-json-logger`
- Docker
- Vector

---

### Task 1: Add `python-json-logger` to `requirements.txt`

**Files:**
- Modify: `requirements.txt`

**Step 1: Add the dependency**

Add the following line to `requirements.txt`:

```
python-json-logger
```

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "feat: add python-json-logger dependency"
```

---

### Task 2: Create the `logger` module

**Files:**
- Create: `modules/logger.py`

**Step 1: Write the logger module**

```python
import logging
import logging.config
import sys
import threading
from pythonjsonlogger import jsonlogger

# Use a thread-local to store the correlation ID
log_context = threading.local()

class CorrelationIdFilter(logging.Filter):
    """
    Injects the correlation_id into the log record.
    """
    def filter(self, record):
        record.correlation_id = getattr(log_context, 'correlation_id', None)
        return True

def get_logger(name):
    """
    Get a configured logger instance.
    """
    # Check if the logger is already configured
    if name in logging.Logger.manager.loggerDict:
        return logging.getLogger(name)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Create a handler to write to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    # Create a JSON formatter
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s %(correlation_id)s'
    )
    handler.setFormatter(formatter)

    # Add the filter and handler
    logger.addFilter(CorrelationIdFilter())
    logger.addHandler(handler)

    # Don't propagate to the root logger
    logger.propagate = False

    return logger

def set_correlation_id(correlation_id):
    """
    Set the correlation ID for the current thread.
    """
    log_context.correlation_id = correlation_id
```

**Step 2: Commit**

```bash
git add modules/logger.py
git commit -m "feat: create logger module"
```

---

### Task 3: Create the Vector configuration file

**Files:**
- Create: `vector.toml`

**Step 1: Write the Vector configuration**

```toml
[sources.docker_logs]
  type = "docker_logs"
  # You can add specific container names to include/exclude if needed
  # include_containers = ["app", "worker"]

[transforms.remap]
  type = "remap"
  inputs = ["docker_logs"]
  source = '''
  . = parse_json!(.message)
  '''

[sinks.console]
  type = "console"
  inputs = ["remap"]
  encoding.codec = "json"
```

**Step 2: Commit**

```bash
git add vector.toml
git commit -m "feat: create vector configuration"
```

---

### Task 4: Update `docker-compose.yml`

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Update the Docker Compose file**

Add the `vector` service and update the logging configuration for the `app` service (and any other services that should be logged).

```yaml
services:
  app:
    # ... (existing app service configuration)
    logging:
      driver: "fluentd"
      options:
        fluentd-address: "localhost:8000"
        tag: "app.{{.Name}}"

  vector:
    image: timberio/vector:latest
    ports:
      - "8000:8000/udp"
    volumes:
      - ./vector.toml:/etc/vector/vector.toml:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
```
*Note: You will need to find the `app` service in the existing `docker-compose.yml` and add the `logging` section to it. You will also need to add the `vector` service.*

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: update docker-compose for logging"
```
---

### Task 5: Add an example usage

**Files:**
- Create: `experiments/logging_example.py`

**Step 1: Write the example**

```python
import uuid
from modules.logger import get_logger, set_correlation_id

def main():
    # Set a correlation ID for this "request"
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    logger = get_logger(__name__)

    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")

    try:
        raise ValueError("This is a test exception.")
    except ValueError:
        logger.exception("An exception occurred.")

if __name__ == "__main__":
    main()

```

**Step 2: Commit**

```bash
git add experiments/logging_example.py
git commit -m "feat: add logging example"
```

---
### Task 6: Test the logging system

**Step 1: Run the example**

Run the logging example in a Docker container. First, build the image, then run the example.

```bash
docker-compose build app
docker-compose run --rm app python experiments/logging_example.py
```

**Step 2: Verify the output**

You should see the JSON logs from the `app` container in the output of the `vector` container.

Run `docker-compose up vector` in a separate terminal to see the logs. The output should look something like this:

```json
{"asctime": "...", "name": "experiments.logging_example", "levelname": "INFO", "message": "This is an info message.", "correlation_id": "..."}
{"asctime": "...", "name": "experiments.logging_example", "levelname": "WARNING", "message": "This is a warning message.", "correlation_id": "..."}
{"asctime": "...", "name": "experiments.logging_example", "levelname": "ERROR", "message": "This is an error message.", "correlation_id": "..."}
{"asctime": "...", "name": "experiments.logging_example", "levelname": "ERROR", "message": "An exception occurred.", "correlation_id": "...", "exc_info": "..."}
```

This confirms that the logging pipeline is working as expected.
