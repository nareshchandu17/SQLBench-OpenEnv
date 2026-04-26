#!/usr/bin/env python3
"""
Deployment script for Hugging Face Spaces
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(command, cwd=None):
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()

def check_huggingface_cli():
    """Check if Hugging Face CLI is installed."""
    success, output = run_command("huggingface-cli --version")
    if not success:
        print("❌ Hugging Face CLI not found. Installing...")
        success, output = run_command("pip install huggingface_hub")
        if not success:
            print("❌ Failed to install Hugging Face CLI")
            return False
        print("✅ Hugging Face CLI installed successfully")
    else:
        print(f"✅ Hugging Face CLI found: {output}")
    return True

def login_to_huggingface():
    """Login to Hugging Face."""
    print("🔐 Logging into Hugging Face...")
    
    # Check if already logged in
    success, output = run_command("huggingface-cli whoami")
    if success:
        print(f"✅ Already logged in as: {output}")
        return True
    
    # Try to login with token
    token = os.environ.get("HF_TOKEN")
    if token:
        print("🔑 Using HF_TOKEN from environment...")
        success, output = run_command(f"echo {token} | huggingface-cli login --token")
        if success:
            print("✅ Successfully logged in with token")
            return True
        else:
            print("❌ Failed to login with token")
            return False
    else:
        print("❌ HF_TOKEN not found in environment variables")
        print("Please set HF_TOKEN or run 'huggingface-cli login' manually")
        return False

def create_space():
    """Create Hugging Face Space."""
    print("🚀 Creating Hugging Face Space...")
    
    space_name = "sqlbench-openenv"
    
    # Check if space already exists
    success, output = run_command(f"huggingface-cli space info {space_name}")
    if success:
        print(f"✅ Space {space_name} already exists")
        return space_name
    
    # Create new space
    create_command = f"""
    huggingface-cli space create \
        --name {space_name} \
        --title "SQLBench-OpenEnv" \
        --description "Comprehensive SQL benchmarking platform for LLM evaluation" \
        --sdk gradio \
        --emoji "🏆" \
        --colorFrom "blue" \
        --colorTo "indigo" \
        --license "mit" \
        --tags "sql,benchmark,llm,evaluation,openenv"
    """
    
    success, output = run_command(create_command)
    if success:
        print(f"✅ Space {space_name} created successfully")
        return space_name
    else:
        print(f"❌ Failed to create space: {output}")
        return None

def push_to_space(space_name):
    """Push code to Hugging Face Space."""
    print(f"📤 Pushing to Hugging Face Space: {space_name}")
    
    # Initialize git repository if not already done
    if not Path(".git").exists():
        success, output = run_command("git init")
        if not success:
            print("❌ Failed to initialize git repository")
            return False
        print("✅ Git repository initialized")
    
    # Add remote if not exists
    success, output = run_command("git remote get-url origin")
    if not success:
        remote_url = f"https://huggingface.co/spaces/{space_name}"
        success, output = run_command(f"git remote add origin {remote_url}")
        if not success:
            print(f"❌ Failed to add remote: {output}")
            return False
        print(f"✅ Added remote: {remote_url}")
    
    # Stage all files
    success, output = run_command("git add .")
    if not success:
        print(f"❌ Failed to stage files: {output}")
        return False
    print("✅ Files staged")
    
    # Commit changes
    success, output = run_command('git commit -m "Deploy to Hugging Face Spaces"')
    if not success:
        print(f"❌ Failed to commit: {output}")
        return False
    print("✅ Changes committed")
    
    # Push to Hugging Face
    success, output = run_command("git push origin main --force")
    if success:
        print("✅ Successfully pushed to Hugging Face Spaces")
        print(f"🌐 Your space is available at: https://huggingface.co/spaces/{space_name}")
        return True
    else:
        print(f"❌ Failed to push: {output}")
        return False

def main():
    """Main deployment function."""
    print("🚀 SQLBench-OpenEnv Hugging Face Spaces Deployment")
    print("=" * 60)
    
    # Check prerequisites
    if not check_huggingface_cli():
        print("❌ Please install Hugging Face CLI first")
        return False
    
    # Login to Hugging Face
    if not login_to_huggingface():
        print("❌ Please login to Hugging Face first")
        return False
    
    # Create space
    space_name = create_space()
    if not space_name:
        print("❌ Failed to create Hugging Face Space")
        return False
    
    # Push to space
    if not push_to_space(space_name):
        print("❌ Failed to push to Hugging Face Space")
        return False
    
    print("\n🎉 Deployment completed successfully!")
    print(f"🌐 Visit your space at: https://huggingface.co/spaces/{space_name}")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
