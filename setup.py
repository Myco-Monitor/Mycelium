#!/usr/bin/env python3
"""
Mycelium Project Setup Script

This script sets up the Mycelium mushroom farm monitoring system by:
1. Creating or using a Python environment (virtualenv or conda)
2. Installing required dependencies in the environment
3. Initializing the database with schema
4. Creating necessary directories and configuration files
5. Validating the installation

Usage:
    python setup.py [--env-type {venv,conda,existing}] [--env-name NAME] [--dev] [--reset-db]

Options:
    --env-type      Environment type: 'venv' (virtualenv), 'conda', or 'existing' (use current)
    --env-name      Environment name (default: 'mycelium')
    --dev           Install development dependencies (pytest, etc.)
    --reset-db      Reset database (WARNING: deletes all existing data)
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path
import sqlite3
import json

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from version import __version__


def detect_environment_tools():
    """Detect available environment management tools."""
    tools = {}

    # Check for conda
    try:
        result = subprocess.run(["conda", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            tools["conda"] = result.stdout.strip()
    except FileNotFoundError:
        pass

    # Check for virtualenv (venv is built into Python 3.3+)
    if sys.version_info >= (3, 3):
        tools["venv"] = f"Python {sys.version.split()[0]} built-in venv"

    return tools


def prompt_environment_choice():
    """Prompt user to choose environment type."""
    tools = detect_environment_tools()

    print("\n🐍 Python Environment Setup")
    print("=" * 40)
    print(
        "To avoid conflicts with your system Python, we'll create an isolated environment."
    )
    print("\nAvailable options:")

    options = []
    if "conda" in tools:
        options.append(("conda", f"Conda environment ({tools['conda']})"))
        print(f"  1. Conda environment ({tools['conda']})")

    if "venv" in tools:
        options.append(("venv", f"Virtual environment ({tools['venv']})"))
        print(f"  {len(options) + 1}. Virtual environment ({tools['venv']})")

    options.append(("existing", "Use current Python environment (not recommended)"))
    print(f"  {len(options) + 1}. Use current Python environment (not recommended)")

    if not options[:-1]:  # Only 'existing' option available
        print("\n⚠️  No environment management tools found!")
        print("We recommend installing conda or ensuring Python 3.3+ is available.")
        return "existing"

    while True:
        try:
            choice = input(f"\nChoose option (1-{len(options)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                env_type = options[idx][0]
                print(f"Selected: {options[idx][1]}")
                return env_type
            else:
                print(f"Please enter a number between 1 and {len(options)}")
        except (ValueError, KeyboardInterrupt):
            print("\nSetup cancelled by user.")
            return None


def create_conda_environment(env_name):
    """Create or update a conda environment."""
    print(f"\n🐍 Setting up conda environment '{env_name}'...")

    # Check if environment already exists
    result = subprocess.run(["conda", "env", "list"], capture_output=True, text=True)
    env_exists = env_name in result.stdout

    if env_exists:
        print(f"📦 Environment '{env_name}' already exists.")
        choice = input("Do you want to update it? (y/N): ").strip().lower()
        if choice not in ["y", "yes"]:
            print("Using existing environment.")
            return True

    # Create environment with Python 3.11 for better package compatibility
    cmd = ["conda", "create", "-n", env_name, "python=3.11", "-y"]
    if not run_command(" ".join(cmd), f"Creating conda environment '{env_name}'"):
        return False

    print(f"✅ Conda environment '{env_name}' ready!")
    return True


def create_venv_environment(env_name):
    """Create or update a virtual environment."""
    print(f"\n🐍 Setting up virtual environment '{env_name}'...")

    env_path = project_root / env_name

    if env_path.exists():
        print(f"📦 Environment '{env_name}' already exists.")
        choice = input("Do you want to recreate it? (y/N): ").strip().lower()
        if choice not in ["y", "yes"]:
            print("Using existing environment.")
            return True
        else:
            # Remove existing environment
            import shutil

            shutil.rmtree(env_path)

    # Create virtual environment
    cmd = [sys.executable, "-m", "venv", str(env_path)]
    if not run_command(" ".join(cmd), f"Creating virtual environment '{env_name}'"):
        return False

    print(f"✅ Virtual environment '{env_name}' ready!")
    return True


def get_environment_python(env_type, env_name):
    """Get the Python executable path for the environment."""
    if env_type == "conda":
        # Get conda environment path
        result = subprocess.run(
            ["conda", "env", "list"], capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if line.strip().startswith(env_name):
                env_path = line.split()[-1]
                if os.name == "nt":  # Windows
                    return os.path.join(env_path, "python.exe")
                else:  # Unix-like
                    return os.path.join(env_path, "bin", "python")
        return None

    elif env_type == "venv":
        env_path = project_root / env_name
        if os.name == "nt":  # Windows
            return env_path / "Scripts" / "python.exe"
        else:  # Unix-like
            return env_path / "bin" / "python"

    else:  # existing
        return sys.executable


def activate_environment_message(env_type, env_name):
    """Provide instructions for activating the environment."""
    if env_type == "conda":
        return f"conda activate {env_name}"
    elif env_type == "venv":
        if os.name == "nt":  # Windows
            return f"{env_name}\\Scripts\\activate"
        else:  # Unix-like
            return f"source {env_name}/bin/activate"
    else:
        return "# Using current environment"


def run_command(command, description=""):
    """Run a shell command and handle errors."""
    print(f"{'=' * 60}")
    print(f"Running: {description or command}")
    print(f"{'=' * 60}")

    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {e}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        return False


def install_dependencies(python_executable, dev=False):
    """Install required Python dependencies in the specified environment."""
    print("\n🔧 Installing Python dependencies...")

    # Check if requirements.txt exists
    req_file = project_root / "requirements.txt"
    if not req_file.exists():
        print("❌ requirements.txt not found. Creating basic requirements...")
        create_requirements_file()

    # Get pip command for the environment
    pip_cmd = f"{python_executable} -m pip"

    # Upgrade pip first
    if not run_command(f"{pip_cmd} install --upgrade pip", "Upgrading pip"):
        print("⚠️  Warning: Failed to upgrade pip, continuing anyway...")

    # Install main dependencies
    if not run_command(
        f"{pip_cmd} install -r requirements.txt", "Installing main dependencies"
    ):
        return False

    # Install development dependencies if requested
    if dev:
        dev_deps = [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
        ]
        for dep in dev_deps:
            if not run_command(f"{pip_cmd} install {dep}", f"Installing {dep}"):
                print(f"⚠️  Warning: Failed to install {dep}")

    print("✅ Dependencies installed successfully!")
    return True


def create_requirements_file():
    """Create requirements.txt if it doesn't exist."""
    requirements = [
        # Core Web Framework (NiceGUI bundles FastAPI + Uvicorn)
        "nicegui>=2.0.0",
        "plotly>=5.17.0",
        # Data Processing
        "pandas>=2.0.0,<2.3.0",
        "numpy>=1.24.0,<2.0.0",
        # Security
        "cryptography>=41.0.0",
        "werkzeug>=2.3.7",
        # Device Communication
        "requests>=2.31.0",
        "aiohttp>=3.9.0",
        "zeroconf>=0.131.0",
        "backoff>=2.2.1",
    ]

    req_file = project_root / "requirements.txt"
    with open(req_file, "w") as f:
        f.write("\n".join(requirements))

    print(f"✅ Created {req_file}")


def initialize_database(reset=False):
    """Initialize the database with schema."""
    print("\n🗄️  Initializing database...")

    db_path = project_root / "data" / "mycelium.db"

    # Create storage directory if it doesn't exist
    db_path.parent.mkdir(exist_ok=True)

    # Create logs directory for application logging
    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Reset database if requested
    if reset and db_path.exists():
        print("⚠️  Resetting database (deleting existing data)...")
        db_path.unlink()

    # Initialize database schema
    try:
        # Import database initialization modules
        sys.path.append(str(project_root / "storage"))

        # Initialize core tables
        from storage.initialize_database import initialize_database as init_db

        init_db(str(db_path), force=reset)

        print("✅ Database schema initialized!")

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

    return True


def create_config_files():
    """Create necessary configuration files."""
    print("\n⚙️  Creating configuration files...")

    # Create config directory
    config_dir = project_root / "config"
    config_dir.mkdir(exist_ok=True)

    # Create app configuration
    app_config = {
        "app": {
            "name": "Mycelium Farm Monitor",
            "version": __version__,
            "debug": True,
            "host": "127.0.0.1",
            "port": 8051,
        },
        "database": {"path": "data/mycelium.db", "backup_interval_hours": 24},
        "security": {
            "secret_key": "your-secret-key-change-in-production",
            "session_timeout_minutes": 60,
        },
        "devices": {
            "discovery_enabled": True,
            "polling_interval_seconds": 30,
            "timeout_seconds": 10,
        },
    }

    config_file = config_dir / "app_config.json"
    with open(config_file, "w") as f:
        json.dump(app_config, f, indent=2)

    print(f"✅ Created {config_file}")


def validate_installation():
    """Validate that the installation is working correctly."""
    print("\n🔍 Validating installation...")

    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required")
        return False

    print(f"✅ Python version: {sys.version}")

    # Check required modules
    required_modules = [
        "nicegui",
        "plotly",
        "pandas",
        "numpy",
        "aiohttp",
        "zeroconf",
        "cryptography",
    ]

    # Check analytics modules
    analytics_modules = ["matplotlib", "seaborn", "sklearn", "scipy"]

    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module} installed")
        except ImportError:
            missing_modules.append(module)
            print(f"❌ {module} missing")

    # Check analytics modules (optional but recommended)
    missing_analytics = []
    for module in analytics_modules:
        try:
            __import__(module)
            print(f"✅ {module} installed (analytics)")
        except ImportError:
            missing_analytics.append(module)
            print(f"⚠️  {module} missing (analytics - optional)")

    if missing_modules:
        print(f"❌ Missing required modules: {', '.join(missing_modules)}")
        return False

    if missing_analytics:
        print(f"⚠️  Missing analytics modules: {', '.join(missing_analytics)}")
        print("   Analytics features may be limited. Run setup again to install.")

    # Check database
    db_path = project_root / "data" / "mycelium.db"
    if db_path.exists():
        print("✅ Database file exists")

        # Test database connection
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            print(f"✅ Database has {len(tables)} tables")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    else:
        print("❌ Database file not found")
        return False

    print("\n🎉 Installation validation completed successfully!")
    return True


def create_activation_script(env_type, env_name):
    """Create a convenient activation script for the environment."""
    print("\n📝 Creating activation script...")

    if env_type == "conda":
        script_content = f"""#!/bin/bash
# Mycelium Project - Conda Environment Activation
echo "🍄 Activating Mycelium environment..."
conda activate {env_name}
echo "✅ Environment '{env_name}' activated!"
echo "Run 'python run.py' to start the application"
"""
        script_name = "activate_mycelium.sh"

    elif env_type == "venv":
        if os.name == "nt":  # Windows
            script_content = f"""@echo off
REM Mycelium Project - Virtual Environment Activation
echo 🍄 Activating Mycelium environment...
call {env_name}\\Scripts\\activate.bat
echo ✅ Environment '{env_name}' activated!
echo Run 'python run.py' to start the application
"""
            script_name = "activate_mycelium.bat"
        else:  # Unix-like
            script_content = f"""#!/bin/bash
# Mycelium Project - Virtual Environment Activation
echo "🍄 Activating Mycelium environment..."
source {env_name}/bin/activate
echo "✅ Environment '{env_name}' activated!"
echo "Run 'python run.py' to start the application"
"""
            script_name = "activate_mycelium.sh"
    else:
        return  # No script needed for existing environment

    script_path = project_root / script_name
    try:
        with open(script_path, "w") as f:
            f.write(script_content)

        # Make executable on Unix-like systems
        if os.name != "nt" and script_name.endswith(".sh"):
            os.chmod(script_path, 0o755)

        print(f"✅ Created activation script: {script_name}")
        print(f"   You can run: source {script_name}")

    except Exception as e:
        print(f"⚠️  Warning: Could not create activation script: {e}")


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Setup Mycelium Project")
    parser.add_argument(
        "--env-type",
        choices=["venv", "conda", "existing"],
        help="Environment type: 'venv' (virtualenv), 'conda', or 'existing' (use current)",
    )
    parser.add_argument(
        "--env-name", default="mycelium", help="Environment name (default: 'mycelium')"
    )
    parser.add_argument(
        "--dev", action="store_true", help="Install development dependencies"
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Reset database (WARNING: deletes existing data)",
    )

    args = parser.parse_args()

    print("🍄 Mycelium Project Setup")
    print("=" * 50)

    # Step 1: Environment setup
    env_type = args.env_type
    if not env_type:
        env_type = prompt_environment_choice()
        if not env_type:
            print("❌ Setup cancelled by user")
            return 1

    env_name = args.env_name
    python_executable = None

    # Create or use environment
    if env_type == "conda":
        if not create_conda_environment(env_name):
            print("❌ Failed to create conda environment")
            return 1
        python_executable = get_environment_python(env_type, env_name)
    elif env_type == "venv":
        if not create_venv_environment(env_name):
            print("❌ Failed to create virtual environment")
            return 1
        python_executable = get_environment_python(env_type, env_name)
    else:  # existing
        print("\n🐍 Using current Python environment")
        python_executable = sys.executable

    if not python_executable or not Path(python_executable).exists():
        print(f"❌ Could not find Python executable for environment '{env_name}'")
        return 1

    print(f"✅ Using Python: {python_executable}")

    # Step 2: Install dependencies
    if not install_dependencies(python_executable, dev=args.dev):
        print("❌ Setup failed during dependency installation")
        return 1

    # Step 3: Create configuration files
    create_config_files()

    # Step 4: Initialize database
    if not initialize_database(reset=args.reset_db):
        print("❌ Setup failed during database initialization")
        return 1

    # Step 5: Validate installation
    if not validate_installation():
        print("❌ Setup validation failed")
        return 1

    print("\n🎉 Setup completed successfully!")
    print("\nNext steps:")

    if env_type != "existing":
        activation_cmd = activate_environment_message(env_type, env_name)
        print(f"1. Activate environment: {activation_cmd}")
        print("2. Run: python run.py")
        print("3. Open browser to: http://localhost:8051")

        # Create activation script
        create_activation_script(env_type, env_name)
    else:
        print("1. Run: python run.py")
        print("2. Open browser to: http://localhost:8051")

    return 0


if __name__ == "__main__":
    sys.exit(main())
