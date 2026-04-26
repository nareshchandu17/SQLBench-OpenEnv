import uvicorn
import os

if __name__ == "__main__":
    # This shim matches the command in README.md
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860, reload=True)
