#!/usr/bin/env python3
"""
Test Runner for Mycelium Database

This script discovers and runs tests for the Mycelium database components.
It can run all tests or specific tests based on command-line arguments.
"""

import os
import sys
import argparse
import importlib.util
import unittest
import time
from pathlib import Path

# Add the project root directory to the path so we can import modules
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Test directory
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tables')

def discover_tests():
    """
    Discover all test files in the tests directory.
    
    Returns:
        list: List of test module names without the .py extension
    """
    test_files = []
    for file in os.listdir(TEST_DIR):
        if file.startswith('test_') and file.endswith('.py'):
            test_files.append(file[:-3])  # Remove .py extension
    return sorted(test_files)

def run_test_module(module_name):
    """
    Run a specific test module.
    
    Args:
        module_name (str): Name of the test module without .py extension
    
    Returns:
        bool: True if test passed, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"Running test: {module_name}")
    print(f"{'='*80}")
    
    try:
        # Import the module
        module_path = os.path.join(TEST_DIR, f"{module_name}.py")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check for test functions in priority order
        test_found = False
        
        # 1. Look for test_X_crud function
        table_name = module_name.replace('test_', '')
        if hasattr(module, f"test_{table_name}_crud"):
            print(f"Running function: test_{table_name}_crud")
            test_func = getattr(module, f"test_{table_name}_crud")
            test_func()
            test_found = True
        # 2. Look for test_X function
        elif hasattr(module, f"test_{table_name}"):
            print(f"Running function: test_{table_name}")
            test_func = getattr(module, f"test_{table_name}")
            test_func()
            test_found = True
        # 3. Look for main function
        elif hasattr(module, 'main'):
            print("Running function: main")
            module.main()
            test_found = True
        # 4. Try unittest framework
        else:
            suite = unittest.TestLoader().loadTestsFromModule(module)
            if suite.countTestCases() > 0:
                print(f"Running {suite.countTestCases()} unittest cases")
                result = unittest.TextTestRunner(verbosity=2).run(suite)
                test_found = True
        
        if test_found:
            print(f"\nTest {module_name} completed successfully")
            return True
        else:
            print(f"\nNo test functions found in {module_name}")
            return False
    except Exception as e:
        print(f"Error running {module_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """
    Run all discovered tests.
    
    Returns:
        tuple: (passed_count, failed_count, failed_tests)
    """
    test_modules = discover_tests()
    passed = 0
    failed = 0
    failed_tests = []
    
    start_time = time.time()
    
    for module_name in test_modules:
        try:
            if run_test_module(module_name):
                passed += 1
            else:
                failed += 1
                failed_tests.append(module_name)
        except Exception as e:
            print(f"Error running {module_name}: {e}")
            failed += 1
            failed_tests.append(f"{module_name} (Exception: {str(e)})")
    
    end_time = time.time()
    
    return passed, failed, failed_tests, end_time - start_time

def main():
    """Main function to parse arguments and run tests."""
    parser = argparse.ArgumentParser(description='Run Mycelium database tests')
    parser.add_argument('--test', type=str, help='Specific test to run (without .py extension)')
    parser.add_argument('--list', action='store_true', help='List available tests')
    parser.add_argument('--category', type=str, help='Run tests for a specific category (e.g., "business", "core", "config")')
    
    args = parser.parse_args()
    
    # List available tests
    if args.list:
        print("Available tests:")
        for test in discover_tests():
            print(f"  - {test}")
        return
    
    # Run a specific test
    if args.test:
        test_name = args.test
        # Handle both formats: with or without 'test_' prefix
        if not test_name.startswith('test_'):
            prefixed_name = f"test_{test_name}"
            # Check if the prefixed name exists
            if prefixed_name + '.py' in os.listdir(TEST_DIR):
                test_name = prefixed_name
        
        if test_name + '.py' in os.listdir(TEST_DIR):
            run_test_module(test_name)
        else:
            print(f"Test '{test_name}' not found. Use --list to see available tests.")
            print("Note: You can specify either the full name (e.g., 'test_farms') or just the table name (e.g., 'farms')")
        return
    
    # Run tests for a specific category
    if args.category:
        category = args.category.lower()
        test_modules = discover_tests()
        category_tests = []
        
        # Map categories to test modules
        category_map = {
            'core': ['test_farms', 'test_grow_rooms', 'test_device_spore', 'test_device_hyphae'],
            'business': ['test_customers', 'test_cost_of_goods', 'test_spawn', 'test_bulk', 
                        'test_harvest', 'test_sales_transaction', 'test_sales_detail', 
                        'test_employees', 'test_labour', 'test_loss_of_goods'],
            'config': ['test_relay_settings', 'test_schedule_settings', 'test_dynamic_settings', 'test_user_settings'],
            'readings': ['test_readings_spore', 'test_readings_hyphae', 'test_readings_weather']
        }
        
        if category in category_map:
            category_tests = [test for test in test_modules if test in category_map[category]]
        else:
            print(f"Unknown category: {category}")
            print("Available categories: core, business, config, readings")
            return
        
        if not category_tests:
            print(f"No tests found for category: {category}")
            return
        
        passed = 0
        failed = 0
        failed_tests = []
        
        for test in category_tests:
            try:
                if run_test_module(test):
                    passed += 1
                else:
                    failed += 1
                    failed_tests.append(test)
            except Exception as e:
                print(f"Error running {test}: {e}")
                failed += 1
                failed_tests.append(f"{test} (Exception: {str(e)})")
        
        print(f"\n{'='*80}")
        print(f"Category '{category}' Test Results: {passed} passed, {failed} failed")
        if failed_tests:
            print("Failed tests:")
            for test in failed_tests:
                print(f"  - {test}")
        print(f"{'='*80}")
        return
    
    # Run all tests
    print(f"Running all tests in {TEST_DIR}...")
    passed, failed, failed_tests, duration = run_all_tests()
    
    print(f"\n{'='*80}")
    print(f"Test Results: {passed} passed, {failed} failed")
    print(f"Total time: {duration:.2f} seconds")
    
    if failed_tests:
        print("\nFailed tests:")
        for test in failed_tests:
            print(f"  - {test}")
    
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
