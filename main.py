"""Start both backend and frontend servers."""

import subprocess
import sys
import signal
import os
import time
import shutil
import socket
import argparse
from pathlib import Path

# Global process references for cleanup
backend_process = None
frontend_process = None


def cleanup_processes():
    """Terminate both backend and frontend processes."""
    global backend_process, frontend_process
    
    print("\nShutting down servers...")
    
    if backend_process:
        try:
            backend_process.terminate()
            backend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_process.kill()
        except Exception as e:
            print(f"Error stopping backend: {e}")
    
    if frontend_process:
        try:
            frontend_process.terminate()
            frontend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            frontend_process.kill()
        except Exception as e:
            print(f"Error stopping frontend: {e}")
    
    print("✓ Servers stopped")
    sys.exit(0)


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    cleanup_processes()


def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    # Try connecting first - if successful, port is in use
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.1)
        if s.connect_ex(('127.0.0.1', port)) == 0:
            return True
    
    # If connection failed, try binding to 0.0.0.0 (same as backend)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except OSError:
            return True


def kill_process_on_port(port: int) -> bool:
    """Kill process using the specified port. Returns True if killed, False otherwise."""
    if sys.platform == "win32":
        # Windows: use netstat to find PID, then taskkill
        try:
            # Find PID using netstat
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse netstat output to find PID for the port
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            # Kill the process
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid],
                                capture_output=True,
                                check=True
                            )
                            print(f"  Killed process {pid} using port {port}")
                            time.sleep(0.5)  # Give it a moment to release the port
                            return True
                        except subprocess.CalledProcessError:
                            pass
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    else:
        # Unix/Linux/Mac: use lsof to find PID, then kill
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                check=True
            )
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    try:
                        subprocess.run(
                            ["kill", "-9", pid],
                            capture_output=True,
                            check=True
                        )
                        print(f"  Killed process {pid} using port {port}")
                        time.sleep(0.5)
                        return True
                    except subprocess.CalledProcessError:
                        pass
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    return False


def main():
    """Start both backend and frontend servers."""
    global backend_process, frontend_process
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Start LLM Council servers")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (verbose logging, auto-reload, source maps)"
    )
    args = parser.parse_args()
    
    debug_mode = args.debug
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting LLM Council...")
    if debug_mode:
        print("🔍 Debug mode enabled")
    print()
    
    # Check if ports are in use and kill processes if needed
    if is_port_in_use(8001):
        print(f"Port 8001 is in use. Attempting to kill process...")
        if kill_process_on_port(8001):
            time.sleep(1)  # Wait for port to be released
            if is_port_in_use(8001):
                print("✗ Port 8001 is still in use after killing process!")
                sys.exit(1)
        else:
            print("✗ Could not kill process on port 8001!")
            print("  Please stop any existing backend server manually.")
            sys.exit(1)
    
    if is_port_in_use(5173):
        print(f"Port 5173 is in use. Attempting to kill process...")
        if kill_process_on_port(5173):
            time.sleep(1)  # Wait for port to be released
            if is_port_in_use(5173):
                print("✗ Port 5173 is still in use after killing process!")
                sys.exit(1)
        else:
            print("✗ Could not kill process on port 5173!")
            print("  Please stop any existing frontend server manually.")
            sys.exit(1)
    
    # Determine which Python to use - prioritize venv if it exists
    venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe" if sys.platform == "win32" else Path(__file__).parent / ".venv" / "bin" / "python"
    
    if venv_python.exists():
        python_cmd = str(venv_python)
    elif sys.platform == "win32":
        python_cmd = "python"
    else:
        python_cmd = "python3"
    
    # Start backend
    print("Starting backend on http://localhost:8001...")
    backend_cmd = [python_cmd, "-m", "backend.main"]
    
    # Set DEBUG environment variable if debug mode is enabled
    backend_env = os.environ.copy()
    if debug_mode:
        backend_env["DEBUG"] = "true"
    
    # In debug mode, show output directly; otherwise capture it
    if debug_mode:
        backend_process = subprocess.Popen(
            backend_cmd,
            env=backend_env,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
    else:
        backend_process = subprocess.Popen(
            backend_cmd,
            env=backend_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
    
    # Wait a bit for backend to start
    time.sleep(2)
    
    # Check if backend started successfully
    if backend_process.poll() is not None:
        print("✗ Backend failed to start!")
        print(backend_process.stdout.read() if backend_process.stdout else "No output")
        sys.exit(1)
    
    # Start frontend
    print("Starting frontend on http://localhost:5173...")
    frontend_dir = Path(__file__).parent / "frontend"
    
    # Check if node_modules exists
    if not (frontend_dir / "node_modules").exists():
        print("⚠ node_modules not found. Run 'npm install' in frontend/ first.")
        cleanup_processes()
        return
    
    # On Windows, use shell=True to ensure PATH is respected for npm
    use_shell = sys.platform == "win32"
    if use_shell:
        frontend_cmd = "npm run dev:debug" if debug_mode else "npm run dev"
    else:
        npm_path = shutil.which("npm")
        if not npm_path:
            print("✗ npm not found in PATH!")
            cleanup_processes()
            return
        frontend_cmd = [npm_path, "run", "dev:debug" if debug_mode else "dev"]
    
    # In debug mode, show output directly; otherwise capture it
    if debug_mode:
        frontend_process = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            text=True,
            bufsize=1,
            universal_newlines=True,
            shell=use_shell
        )
    else:
        frontend_process = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            shell=use_shell
        )
    
    print()
    print("✓ LLM Council is running!")
    print("  Backend:  http://localhost:8001")
    print("  Frontend: http://localhost:5173")
    if debug_mode:
        print("  🔍 Debug mode: Logs visible, auto-reload enabled")
    print()
    print("Press Ctrl+C to stop both servers")
    print()
    
    # Stream output from both processes
    try:
        while True:
            # Check if processes are still alive
            if backend_process.poll() is not None:
                print("✗ Backend process exited!")
                break
            if frontend_process.poll() is not None:
                print("✗ Frontend process exited!")
                break
            
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_processes()


if __name__ == "__main__":
    main()
