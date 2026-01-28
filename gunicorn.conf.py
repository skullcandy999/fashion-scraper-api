# Gunicorn configuration
bind = "0.0.0.0:10000"
workers = 15
timeout = 300  # 5 min - allows large batches (100-150 SKUs)
preload_app = True
