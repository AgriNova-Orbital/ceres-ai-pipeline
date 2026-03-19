# Logging System Design

This document outlines the design for a new logging system for this project.

## Part 1: Application Logging Design

The core of our logging system will be Python's built-in `logging` module. We'll create a standardized logging configuration that can be used across all Python applications in the project.

Here's the plan:

1.  **Create a central logging configuration:** We'll create a new module, `modules/logger.py`, to encapsulate the logging setup. This module will provide a function, `get_logger()`, that takes a logger name as input and returns a configured logger instance.
2.  **JSON Formatting:** The logger will be configured to use a JSON formatter. We'll use the `python-json-logger` library for this.
3.  **Structured Log Records:** The JSON logs will include the following fields by default:
    *   `timestamp`: The time the log was generated (in UTC).
    *   `level`: The log level (e.g., `INFO`, `ERROR`).
    *   `name`: The name of the logger (e.g., `apps.my_app`).
    *   `message`: The log message.
4.  **Correlation ID:** To trace requests across different services, we'll add a correlation ID to our logs. We'll use a `threading.local()` to store the correlation ID for the current request and a `logging.Filter` to automatically inject the correlation ID into the log record.
5.  **Example Usage:** We will provide an example of how to use the logger in an application.

## Part 2: Infrastructure Logging Design

Now that we have the application logging configured, we need to set up the infrastructure to collect, process, and view the logs.

Here's the plan:

1.  **Logging Agent:** We'll use **Vector** as our logging agent. Vector is a high-performance, open-source tool for building observability pipelines. It's written in Rust and is known for its reliability and small resource footprint.
2.  **Docker Compose:** We'll update the `docker-compose.yml` file to include a `vector` service.
3.  **Vector Configuration:** We'll create a `vector.toml` configuration file for Vector. This file will define the following:
    *   **Sources:** A `docker_logs` source to collect logs from all other containers in the Docker Compose project.
    *   **Transforms:** A `remap` transform to parse the JSON log messages and add metadata.
    *   **Sinks:** A `console` sink to print the processed logs to standard output for now. This makes it easy to see the logs in real-time during development. We can easily add other sinks later to send logs to a centralized logging service like Elasticsearch, Loki, or a cloud provider's logging service.
4.  **Application Container Configuration:** We'll update the application services in `docker-compose.yml` to use the `docker/fluentd` logging driver. This driver will send logs to the Vector container.
5.  **Example `docker-compose.yml` changes:**

    ```yaml
    services:
      app:
        # ...
        logging:
          driver: "fluentd"
          options:
            fluentd-address: localhost:8000
            tag: "app.{{.Name}}"

      vector:
        image: timberio/vector:latest
        ports:
          - "8000:8000/udp"
        volumes:
          - ./vector.toml:/etc/vector/vector.toml:ro
          - /var/run/docker.sock:/var/run/docker.sock:ro
    ```
