# Worker Background Tasks Documentation

The `workers` module (`apps/api/workers/worker`) listens to Redis task queues to run asynchronous profiling and cloud migration jobs outside of FastAPI HTTP request handlers.
