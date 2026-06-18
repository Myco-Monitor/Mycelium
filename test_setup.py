#!/usr/bin/env python3
"""
Mycelium Project Test Script

This script runs basic tests to verify the setup is working correctly.

Usage:
    python test_setup.py [--verbose]
"""

import sys
import os
import argparse
import sqlite3
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def test_imports(verbose=False):
    """Test that all required modules can be imported."""
    print("🔍 Testing module imports...")
    
    modules_to_test = [
        ('dash', 'Dash web framework'),
        ('dash_bootstrap_components', 'Bootstrap components for Dash'),
        ('plotly', 'Plotting library'),
        ('pandas', 'Data manipulation library'),
        ('numpy', 'Numerical computing library'),
        ('flask_login', 'User session management'),
        ('web_app.utils.business_utils', 'Business data access layer'),
        ('web_app.pages.production', 'Production management page'),
        ('web_app.pages.inventory', 'Inventory management page'),
        ('web_app.pages.sales', 'Sales management page'),
        ('web_app.pages.employees', 'Employee management page'),
        ('web_app.pages.financials', 'Financial reporting page')
    ]
    
    failed_imports = []
    
    for module_name, description in modules_to_test:
        try:
            __import__(module_name)
            if verbose:
                print(f"  ✅ {module_name} - {description}")
        except ImportError as e:
            failed_imports.append((module_name, str(e)))
            print(f"  ❌ {module_name} - {description}: {e}")
    
    if failed_imports:
        print(f"\n❌ {len(failed_imports)} import(s) failed!")
        return False
    else:
        print(f"✅ All {len(modules_to_test)} modules imported successfully!")
        return True

def test_database(verbose=False):
    """Test database connectivity and structure."""
    print("\n🗄️  Testing database...")
    
    db_path = project_root / "data" / "mycelium.db"
    
    if not db_path.exists():
        print("❌ Database file not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if main business tables exist
        expected_tables = [
            'spawn', 'bulk', 'harvest', 'cost_of_goods', 
            'customers', 'employees', 'labour', 'loss_of_goods'
        ]
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = [table for table in expected_tables if table not in existing_tables]
        
        if missing_tables:
            print(f"❌ Missing tables: {', '.join(missing_tables)}")
            conn.close()
            return False
        
        if verbose:
            print(f"  ✅ Found {len(existing_tables)} tables")
            for table in expected_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"    - {table}: {count} records")
        
        conn.close()
        print("✅ Database structure verified!")
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_business_utils(verbose=False):
    """Test business utilities functionality."""
    print("\n🏢 Testing business utilities...")
    
    try:
        from web_app.utils.business_utils import business_manager
        
        # Test basic operations
        spawn_batches = business_manager.get_spawn_batches()
        customers = business_manager.get_customers()
        employees = business_manager.get_employees()
        
        if verbose:
            print(f"  ✅ Spawn batches: {len(spawn_batches)}")
            print(f"  ✅ Customers: {len(customers)}")
            print(f"  ✅ Employees: {len(employees)}")
        
        print("✅ Business utilities working!")
        return True
        
    except Exception as e:
        print(f"❌ Business utilities test failed: {e}")
        return False

def test_web_pages(verbose=False):
    """Test that web pages can be created without errors."""
    print("\n🌐 Testing web page creation...")
    
    pages_to_test = [
        ('production', 'Production management'),
        ('inventory', 'Inventory management'),
        ('sales', 'Sales management'),
        ('employees', 'Employee management'),
        ('financials', 'Financial reporting')
    ]
    
    failed_pages = []
    
    for page_name, description in pages_to_test:
        try:
            module = __import__(f'web_app.pages.{page_name}', fromlist=['create_layout'])
            layout = module.create_layout()
            
            if verbose:
                print(f"  ✅ {page_name} - {description}")
                
        except Exception as e:
            failed_pages.append((page_name, str(e)))
            print(f"  ❌ {page_name} - {description}: {e}")
    
    if failed_pages:
        print(f"\n❌ {len(failed_pages)} page(s) failed to load!")
        return False
    else:
        print(f"✅ All {len(pages_to_test)} pages created successfully!")
        return True

def test_app_startup(verbose=False):
    """Test that the main app can be imported and configured."""
    print("\n🚀 Testing app startup...")
    
    try:
        from web_app.app import app
        
        # Check that the app is configured
        if hasattr(app, 'server'):
            print("✅ Dash app created successfully!")
            if verbose:
                print(f"  - App title: {getattr(app, 'title', 'Not set')}")
                print(f"  - Server type: {type(app.server).__name__}")
            return True
        else:
            print("❌ App server not properly configured!")
            return False
            
    except Exception as e:
        print(f"❌ App startup test failed: {e}")
        return False

def run_all_tests(verbose=False):
    """Run all tests and return overall result."""
    print("🧪 Running Mycelium Project Tests")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_database,
        test_business_utils,
        test_web_pages,
        test_app_startup
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func(verbose=verbose)
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 All {total} tests passed!")
        print("\n✅ Your Mycelium setup is ready to use!")
        print("Run: python run.py")
        return True
    else:
        print(f"❌ {total - passed} of {total} tests failed!")
        print("\n🔧 Please check the setup and try again.")
        print("Run: python setup.py --sample-data")
        return False

def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test Mycelium Project Setup")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed test output")
    
    args = parser.parse_args()
    
    success = run_all_tests(verbose=args.verbose)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
