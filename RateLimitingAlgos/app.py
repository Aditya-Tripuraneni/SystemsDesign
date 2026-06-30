from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from RateLimitingAlgos.token_bucket import RateLimiterManagerTokenBucket

app = FastAPI()
manager = RateLimiterManagerTokenBucket()


@app.on_event("startup")
async def startup_event():
    pass


@app.on_event("shutdown")
async def shutdown_event():
    await manager.stopAll()


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
          button { padding: 12px 20px; font-size: 16px; }
          #result { margin-top: 20px; font-size: 18px; }
          .allowed { color: green; }
          .blocked { color: crimson; }
        </style>
      </head>
      <body>
        <h1>Token Bucket Demo</h1>
        <button id="requestBtn">Send Request</button>
        <div id="result">Click the button to test the limiter.</div>
        <script>
          const btn = document.getElementById("requestBtn");
          const result = document.getElementById("result");

          btn.addEventListener("click", async () => {
            const response = await fetch("/request", { method: "POST" });
            const data = await response.json();

            result.textContent = data.message;
            result.className = data.allowed ? "allowed" : "blocked";
          });
        </script>
      </body>
    </html>
    """


@app.post("/request")
async def request_token(request: Request):
    client_key = request.client.host if request.client else "unknown"
    limiter = await manager.getOrCreateUser(client_key)
    allowed = await limiter.process_request()
    if allowed:
        return {"allowed": True, "message": f"Request allowed for {client_key}"}

    return {"allowed": False, "message": f"Rate limited for {client_key}"}
