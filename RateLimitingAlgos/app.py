import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from RateLimitingAlgos.leaky_bucket import RateLimiterManagerLeakyBucket
from RateLimitingAlgos.slidingWindowRateLimiter import RateLimiterManagerSlidingWindow
from RateLimitingAlgos.token_bucket import RateLimiterManagerTokenBucket

app = FastAPI()
token_manager = RateLimiterManagerTokenBucket()
leaky_manager = RateLimiterManagerLeakyBucket()
sliding_manager = RateLimiterManagerSlidingWindow(maxReqWindow=2, timeWindow=5)


@app.on_event("startup")
async def startup_event():
    pass


@app.on_event("shutdown")
async def shutdown_event():
    await token_manager.stopAll()
    await leaky_manager.stopAll()
    await sliding_manager.stopAll()


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Rate Limiter Demo</title>
        <style>
          body { font-family: Arial, sans-serif; max-width: 720px; margin: 40px auto; }
          button { padding: 12px 20px; font-size: 16px; margin-right: 8px; }
          #result { margin-top: 20px; font-size: 18px; }
          .allowed { color: green; }
          .blocked { color: crimson; }
        </style>
      </head>
      <body>
        <h1>Rate Limiter Demos</h1>
        <button data-endpoint="/request/token">Token Bucket</button>
        <button data-endpoint="/request/leaky">Leaky Bucket</button>
        <button data-endpoint="/request/sliding">Sliding Window</button>
        <div id="result">Click a button to test the limiter.</div>
        <script>
          const buttons = document.querySelectorAll("button[data-endpoint]");
          const result = document.getElementById("result");

          buttons.forEach((btn) => {
            btn.addEventListener("click", async () => {
              const response = await fetch(btn.dataset.endpoint, { method: "POST" });
              const data = await response.json();

              result.textContent = data.message;
              result.className = data.allowed ? "allowed" : "blocked";
            });
          });
        </script>
      </body>
    </html>
    """


@app.post("/request/token")
async def request_token(request: Request):
    client_key = request.client.host if request.client else "unknown"
    limiter = await token_manager.getOrCreateUser(client_key)
    allowed = await limiter.process_request()
    if allowed:
        return {"allowed": True, "message": f"Token bucket allowed for {client_key}"}

    return {"allowed": False, "message": f"Token bucket rate limited for {client_key}"}


@app.post("/request/leaky")
async def request_leaky(request: Request):
    client_key = request.client.host if request.client else "unknown"
    limiter = await leaky_manager.getOrCreateUser(client_key)
    allowed = await limiter.process_request()
    if allowed:
        return {"allowed": True, "message": f"Leaky bucket allowed for {client_key}"}

    return {"allowed": False, "message": f"Leaky bucket rate limited for {client_key}"}


@app.post("/request/sliding")
async def request_sliding(request: Request):
    client_key = request.client.host if request.client else "unknown"
    limiter = await sliding_manager.getOrCreateUser(client_key)
    allowed = limiter.allow_request(int(time.time()))
    if allowed:
        return {"allowed": True, "message": f"Sliding window allowed for {client_key}"}

    return {"allowed": False, "message": f"Sliding window rate limited for {client_key}"}
