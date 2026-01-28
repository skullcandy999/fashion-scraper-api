# Gunicorn configuration
bind = "0.0.0.0:10000"
workers = 4
worker_class = "gevent"  # Async workers - handles many concurrent requests with low memory
worker_connections = 100  # Each worker handles up to 100 connections
timeout = 300  # 5 min - allows large batches (100-150 SKUs)
preload_app = True
