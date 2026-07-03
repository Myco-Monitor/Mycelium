# Mycelium Project Makefile
# Simple commands for common development tasks

.PHONY: help setup setup-conda setup-venv setup-existing setup-dev reset run dev clean clean-env release

# Default target
help:
	@echo "🍄 Mycelium Project Commands"
	@echo "=========================="
	@echo ""
	@echo "Environment Setup:"
	@echo "  make setup-conda    - Setup with conda environment"
	@echo "  make setup-venv     - Setup with virtual environment"
	@echo "  make setup-existing - Setup using current environment"
	@echo "  make setup          - Interactive setup (prompts for choice)"
	@echo ""
	@echo "Development Setup:"
	@echo "  make setup-dev      - Setup with development dependencies"
	@echo "  make reset          - Reset database (WARNING: deletes all data)"
	@echo ""
	@echo "Running:"
	@echo "  make run            - Start the application"
	@echo "  make dev            - Start in development mode"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean          - Clean up temporary files"
	@echo "  make clean-env      - Remove mycelium environment"
	@echo ""
	@echo "Release:"
	@echo "  make release        - Tag a release from version.py (does not push)"
	@echo ""

# Interactive setup (prompts for environment choice)
setup:
	@echo "🔧 Setting up Mycelium project (interactive)..."
	python setup.py

# Setup with conda environment
setup-conda:
	@echo "🐍 Setting up Mycelium with conda environment..."
	python setup.py --env-type conda

# Setup with virtual environment
setup-venv:
	@echo "🐍 Setting up Mycelium with virtual environment..."
	python setup.py --env-type venv

# Setup using current environment
setup-existing:
	@echo "🐍 Setting up Mycelium with current environment..."
	python setup.py --env-type existing

# Setup with development dependencies
setup-dev:
	@echo "🛠️  Setting up Mycelium for development..."
	python setup.py --dev

# Reset database
reset:
	@echo "⚠️  Resetting database..."
	python setup.py --env-type existing --reset-db

# Run the application
run:
	@echo "🚀 Starting Mycelium..."
	python run.py

# Run in development mode
dev:
	@echo "🚀 Starting Mycelium in development mode..."
	python run.py --dev

# Clean up temporary files
clean:
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.log" -delete
	@echo "✅ Cleanup complete!"

# Remove mycelium environment
clean-env:
	@echo "⚠️  Removing mycelium environment..."
	@if [ -d "mycelium" ]; then \
		echo "Removing virtual environment..."; \
		rm -rf mycelium; \
	fi
	@if command -v conda >/dev/null 2>&1; then \
		if conda env list | grep -q "mycelium"; then \
			echo "Removing conda environment..."; \
			conda env remove -n mycelium -y; \
		fi; \
	fi
	@echo "✅ Environment cleanup complete!"

# Tag a release from version.py (does not push — see scripts/release.sh)
release:
	@echo "🏷️  Tagging release from version.py..."
	./scripts/release.sh
