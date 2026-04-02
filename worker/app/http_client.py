import httpx

# Global HTTP client to enable connection pooling (Keep-Alive) across all modules.
# Limits are tuned for concurrent background processing.
http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    timeout=20.0
)
