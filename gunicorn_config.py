# gunicorn_config.py
timeout = 120  # 120 seconds (2 minutes) instead of default 30
workers = 1
threads = 2
worker_class = 'sync'
bind = "0.0.0.0:10000"
