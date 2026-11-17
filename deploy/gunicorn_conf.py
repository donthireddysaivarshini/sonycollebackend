"""
Gunicorn configuration for Sony Feeding Kurtis production server.
"""

import multiprocessing

# Bind to unix socket
bind = "unix:/run/gunicorn-sony-backend.sock"

# Worker processes: standard recommended formula (2 x CPU cores + 1)
workers = min(multiprocessing.cpu_count() * 2 + 1, 4)
worker_class = "sync"
worker_connections = 1000
timeout = 60
keepalive = 5

# Logging
accesslog = "/var/log/gunicorn/sony-backend-access.log"
errorlog = "/var/log/gunicorn/sony-backend-error.log"
loglevel = "info"

# Process naming
proc_name = "sony_feeding_kurtis_backend"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
