#!/usr/bin/env python3
"""
Main application for Hugging Face Spaces deployment
"""

import os
import sys
import subprocess

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Main entry point for Hugging Face Spaces"""
    print("🚀 Starting SQLBench-OpenEnv on Hugging Face Spaces...")
    
    # Set environment variables for Hugging Face Spaces
    os.environ.setdefault('PYTHONPATH', os.path.dirname(os.path.abspath(__file__)))
    
    # Import and run the server
    try:
        from server.app import app
        import uvicorn
        
        # Get port from environment or default to 7860 (Hugging Face Spaces default)
        port = int(os.environ.get("PORT", 7860))
        host = os.environ.get("HOST", "0.0.0.0")
        
        print(f"🌐 Starting server on {host}:{port}")
        print(f"📊 SQLBench-OpenEnv will be available at: http://localhost:{port}")
        
        # Run the server
        uvicorn.run(app, host=host, port=port)
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("🔧 Make sure all dependencies are installed")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
