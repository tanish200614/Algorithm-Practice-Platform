from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
import subprocess, tempfile, time, psutil, sys

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeRequest(BaseModel):
    code: str

@app.post("/run")
def run_code(req: CodeRequest):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(req.code)
        file_path = f.name

    start = time.time()
    proc = psutil.Popen([sys.executable, file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate(timeout=2)
    duration = round((time.time() - start) * 1000, 2)
    try:
        mem = proc.memory_info().rss // 1024
    except Exception:
        mem = 0
    return {
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
        "time_ms": duration,
        "memory_kb": mem
    }

@app.get("/")
def home():
    return {"message": "Algorithm Practice Backend is running"}
