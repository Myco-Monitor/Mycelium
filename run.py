#!/usr/bin/env python3
"""
Mycelium Project Run Script

This script starts the Mycelium web application (NiceGUI + FastAPI).

Usage:
    python run.py [--host HOST] [--port PORT] [--debug] [--dev] [--sentinel]

Options:
    --host HOST     Host to bind to (default: 127.0.0.1)
    --port PORT     Port to bind to (default: 8051)
    --debug         Enable debug mode
    --dev           Development mode (auto-reload, verbose logging)
    --sentinel      Use Sentinel simulators for testing (localhost devices)
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def load_config():
    """Load application configuration."""
    config_file = project_root / "config" / "app_config.json"

    default_config = {
        "app": {
            "name": "Mycelium Farm Monitor",
            "version": "2.0.0",
            "debug": False,
            "host": "127.0.0.1",
            "port": 8051
        }
    }

    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
            print("Using default configuration...")

    return default_config


def detect_environment():
    """Detect if we're running in a virtual environment."""
    env_info = {
        'type': 'system',
        'name': None,
        'path': None
    }

    conda_env = os.environ.get('CONDA_DEFAULT_ENV')
    if conda_env and conda_env != 'base':
        env_info['type'] = 'conda'
        env_info['name'] = conda_env
        env_info['path'] = os.environ.get('CONDA_PREFIX')
        return env_info

    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        env_info['type'] = 'venv'
        env_info['path'] = sys.prefix
        env_name = Path(sys.prefix).name
        if env_name:
            env_info['name'] = env_name
        return env_info

    return env_info


def check_prerequisites():
    """Check if the system is ready to run."""
    print("Checking prerequisites...")

    env_info = detect_environment()
    if env_info['type'] == 'system':
        print("  Running in system Python environment")
    else:
        print(f"  Running in {env_info['type']} environment: {env_info['name']}")

    # Check database
    db_path = project_root / "data" / "mycelium.db"
    if not db_path.exists():
        print("  Database not found! Run: python setup.py --sample-data")
        return False

    # Check required modules
    required = ['nicegui', 'plotly', 'pandas']

    missing = []
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)

    if missing:
        print(f"  Missing modules: {', '.join(missing)}")
        print("  Run: pip install -r requirements.txt")
        return False

    print("  Prerequisites OK")
    return True


def start_nicegui(host="127.0.0.1", port=8051, debug=False, dev=False):
    """Start the NiceGUI application."""
    if not check_prerequisites():
        return 1

    print(f"Starting Mycelium Farm Monitor...")
    print(f"  Server: http://{host}:{port}")
    print(f"  Debug: {'ON' if debug or dev else 'OFF'}")

    try:
        # Import the NiceGUI app module (registers all routes)
        import web_ui.app  # noqa: F401
        from nicegui import ui

        print("")
        print("=" * 60)
        print("  Mycelium Farm Monitor is running!")
        print("=" * 60)
        print(f"  Open your browser to: http://{host}:{port}")
        print("  Press Ctrl+C to stop")
        print("=" * 60)

        ui.run(
            host=host,
            port=port,
            title='Mycelium - Mushroom Farm Monitor',
            reload=dev,
            show=False,
            storage_secret='mycelium-storage-secret-change-in-production',
        )

    except KeyboardInterrupt:
        print("\nShutting down Mycelium Farm Monitor...")
        return 0
    except Exception as e:
        print(f"Failed to start application: {e}")
        if debug or dev:
            import traceback
            traceback.print_exc()
        return 1


def main():
    """Main run function."""
    parser = argparse.ArgumentParser(description="Run Mycelium Project")
    parser.add_argument("--host", default=None,
                        help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None,
                        help="Port to bind to (default: 8051)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug mode")
    parser.add_argument("--dev", action="store_true",
                        help="Development mode (auto-reload, verbose logging)")
    parser.add_argument("--sentinel", action="store_true",
                        help="Use Sentinel simulators for testing (localhost devices)")

    args = parser.parse_args()

    if args.sentinel:
        os.environ['MYCELIUM_SENTINEL_MODE'] = '1'
        print("Sentinel mode enabled - using simulated devices")

    config = load_config()
    app_config = config.get("app", {})

    host = args.host or app_config.get("host", "127.0.0.1")
    port = args.port or 8051
    debug = args.debug or app_config.get("debug", False)

    return start_nicegui(host=host, port=port, debug=debug, dev=args.dev)


if __name__ == "__main__":
    sys.exit(main())
