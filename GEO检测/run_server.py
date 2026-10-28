import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

proc = subprocess.Popen(
    [
        sys.executable, "-m", "streamlit", "run", "dashboard.py",
        "--server.port", "8501",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
)

print("Streamlit starting...")
for line in proc.stdout:
    print(line, end="")
    if "Local URL" in line or "Network URL" in line:
        print(">>> Dashboard is ready at http://localhost:8501")
