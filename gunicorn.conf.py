# Gunicorn configuration
bind = "0.0.0.0:10000"
workers = 4  # Balance: faster than 2, safer than 15 for 512MB limit
timeout = 300  # 5 min - allows large batches (100-150 SKUs)
preload_app = True
