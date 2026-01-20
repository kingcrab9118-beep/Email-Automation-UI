#!/usr/bin/env python3
"""
Test runner for Email Automation Admin UI
Runs all tests with proper configuration and reporting
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Run all tests with proper setup"""
    
    # Ensure we're in the UI directory
    ui_dir = Path(__file__).parent
    os.chdir(ui_dir)
    
    # Add current directory to Python path
    sys.path.insert(0, str(ui_dir))
    
    print("="*60)
    print("EMAIL AUTOMATION ADMIN UI - TEST SUITE")
    print("="*60)
    
    # Check if pytest is available
    try:
        import pytest
    except ImportError:
        print("ERROR: pytest not installed. Install with: pip install pytest pytest-asyncio")
        sys.exit(1)
    
    # Run tests with pytest
    test_args = [
        '-v',                    # Verbose output
        '--tb=short',           # Short traceback format
        '--strict-markers',     # Strict marker checking
        '--disable-warnings',   # Disable warnings for cleaner output
        'tests/',              # Test directory
    ]
    
    # Add coverage if available
    try:
        import pytest_cov
        test_args.extend(['--cov=.', '--cov-report=term-missing'])
        print("Running tests with coverage reporting...")
    except ImportError:
        print("Running tests without coverage (install pytest-cov for coverage)")
    
    print(f"Test command: pytest {' '.join(test_args)}")
    print("-" * 60)
    
    # Run the tests
    exit_code = pytest.main(test_args)
    
    print("-" * 60)
    if exit_code == 0:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")
    
    print("="*60)
    
    return exit_code

if __name__ == '__main__':
    sys.exit(main())