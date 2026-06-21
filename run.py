#!/usr/bin/env python3
"""
Mycelium Project Run Script

This script starts the Mycelium web application (NiceGUI + FastAPI).

Usage:
    python run.py [--host HOST] [--port PORT] [--debug] [--dev]
                  [--https] [--cert PATH] [--key PATH]

Options:
    --host HOST     Host to bind to (default: 127.0.0.1)
    --port PORT     Port to bind to (default: 8051 HTTP / 8443 HTTPS)
    --debug         Enable debug mode
    --dev           Development mode (auto-reload, verbose logging)
    --https         Serve over HTTPS/TLS (self-signed cert auto-generated)
    --cert PATH     TLS certificate (PEM); implies --https. Default: self-signed
    --key PATH      TLS private key (PEM)
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

from version import __version__  # noqa: E402  (after sys.path setup above)

# Shared Myco-Monitor favicon (same icon used by the Spore/Hyphae web UIs).
FAVICON = project_root / "web_ui" / "assets" / "favicon.ico"


def load_config():
    """Load application configuration."""
    config_file = project_root / "config" / "app_config.json"

    default_config = {
        "app": {
            "name": "Mycelium Farm Monitor",
            "version": __version__,
            "debug": False,
            "host": "127.0.0.1",
            "port": 8051,
        }
    }

    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            # Version is owned by version.py, not the config file
            config.setdefault("app", {})["version"] = __version__
            return config
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
            print("Using default configuration...")

    return default_config


def detect_environment():
    """Detect if we're running in a virtual environment."""
    env_info = {"type": "system", "name": None, "path": None}

    conda_env = os.environ.get("CONDA_DEFAULT_ENV")
    if conda_env and conda_env != "base":
        env_info["type"] = "conda"
        env_info["name"] = conda_env
        env_info["path"] = os.environ.get("CONDA_PREFIX")
        return env_info

    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        env_info["type"] = "venv"
        env_info["path"] = sys.prefix
        env_name = Path(sys.prefix).name
        if env_name:
            env_info["name"] = env_name
        return env_info

    return env_info


def check_prerequisites():
    """Check if the system is ready to run."""
    print("Checking prerequisites...")

    env_info = detect_environment()
    if env_info["type"] == "system":
        print("  Running in system Python environment")
    else:
        print(f"  Running in {env_info['type']} environment: {env_info['name']}")

    # Check database
    db_path = project_root / "data" / "mycelium.db"
    if not db_path.exists():
        print("  Database not found! Run: python setup.py")
        return False

    # Check required modules
    required = ["nicegui", "plotly", "pandas"]

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


def start_nicegui(
    host="127.0.0.1",
    port=8051,
    debug=False,
    dev=False,
    https=False,
    cert_file=None,
    key_file=None,
):
    """Start the NiceGUI application."""
    if not check_prerequisites():
        return 1

    from storage.crypto import get_or_create_storage_secret

    scheme = "https" if https else "http"
    run_kwargs = {}

    bring_your_own_cert = bool(cert_file or key_file)
    local_ca = None
    if https:
        # Issue a leaf from the per-install local CA on first run, or use a
        # provided cert (e.g. a Myco-Monitor CA-issued one). See cert_manager.
        from cert_manager import ensure_cert, local_ca_path

        cert_file, key_file = ensure_cert(cert_file, key_file)
        run_kwargs["ssl_certfile"] = cert_file
        run_kwargs["ssl_keyfile"] = key_file
        if not bring_your_own_cert:
            local_ca = local_ca_path()

    print("Starting Mycelium Farm Monitor...")
    print(f"  Server: {scheme}://{host}:{port}")
    print(f"  Debug: {'ON' if debug or dev else 'OFF'}")
    if https:
        print(f"  TLS cert: {cert_file}")
        if local_ca:
            print(f"  To remove browser warnings, import this CA once: {local_ca}")

    # Advertise mycelium.local on the LAN when serving HTTPS beyond loopback, so
    # any computer on the network can reach it by name. Skipped in dev/reload to
    # avoid double-registration when the reloader re-execs.
    advertise = https and not dev and host not in ("127.0.0.1", "localhost")
    if advertise:
        import mdns_advertise
        from nicegui import app as _app

        if mdns_advertise.start(port):
            _app.on_shutdown(mdns_advertise.stop)

    try:
        # Import the NiceGUI app module (registers all routes)
        import web_ui.app  # noqa: F401
        from nicegui import ui

        print("")
        print("=" * 60)
        print("  Mycelium Farm Monitor is running!")
        print("=" * 60)
        print(f"  Open your browser to: {scheme}://{host}:{port}")
        if advertise:
            print(f"  Or from any LAN computer: {scheme}://mycelium.local:{port}")
        print("  Press Ctrl+C to stop")
        print("=" * 60)

        ui.run(
            host=host,
            port=port,
            title="Mycelium - Mushroom Farm Monitor",
            favicon=str(FAVICON) if FAVICON.exists() else None,
            reload=dev,
            show=False,
            storage_secret=get_or_create_storage_secret(),
            **run_kwargs,
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
    parser.add_argument(
        "--host",
        default=None,
        help="Interface to bind to (default: 127.0.0.1; use 0.0.0.0 for the whole LAN)",
    )
    parser.add_argument(
        "--port", type=int, default=None, help="Port to bind to (default: 8051)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Development mode (auto-reload, verbose logging)",
    )
    parser.add_argument(
        "--https",
        action="store_true",
        help="Serve over HTTPS/TLS (default port 8443; self-signed cert auto-generated)",
    )
    parser.add_argument(
        "--cert",
        default=None,
        help="Path to a TLS certificate (PEM). Implies --https. "
        "Default: auto self-signed in config/.",
    )
    parser.add_argument(
        "--key", default=None, help="Path to the TLS private key (PEM)."
    )

    args = parser.parse_args()

    config = load_config()
    app_config = config.get("app", {})

    https = args.https or bool(args.cert) or app_config.get("https", False)

    host = args.host or app_config.get("host", "127.0.0.1")
    if args.port:
        port = args.port
    elif https:
        port = 8443
    else:
        port = app_config.get("port", 8051)
    debug = args.debug or app_config.get("debug", False)

    # --host is the interface to bind to, not the name clients use. A hostname
    # that doesn't resolve to a local interface (e.g. "mycelium.local") can't be
    # bound -- turn the cryptic getaddrinfo failure into actionable guidance.
    import socket as _socket

    try:
        _socket.getaddrinfo(host, port, type=_socket.SOCK_STREAM)
    except _socket.gaierror:
        print(f"ERROR: cannot bind to --host '{host}' (not a local interface address).")
        print("")
        print("--host is the interface to listen on, not the address browsers use.")
        print("To serve over the network and be reachable as mycelium.local, run:")
        print("    python run.py --https --host 0.0.0.0")
        print("then open https://mycelium.local:8443 from any computer on the LAN.")
        return 1

    return start_nicegui(
        host=host,
        port=port,
        debug=debug,
        dev=args.dev,
        https=https,
        cert_file=args.cert,
        key_file=args.key,
    )


if __name__ == "__main__":
    sys.exit(main())
