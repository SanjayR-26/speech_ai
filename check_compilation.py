#!/usr/bin/env python3
"""
Comprehensive compilation check for FastAPI application
"""
import os
import sys
import importlib.util
from pathlib import Path

def check_file_compilation(file_path):
    """Check if a Python file compiles without errors"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        compile(source, file_path, 'exec')
        return True, None
    except Exception as e:
        return False, str(e)

def check_module_import(module_path):
    """Check if a module can be imported"""
    try:
        spec = importlib.util.spec_from_file_location("test_module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return True, None
    except Exception as e:
        return False, str(e)

def main():
    """Main compilation check"""
    fastapi_dir = Path("fastapi_app")
    
    if not fastapi_dir.exists():
        print("FastAPI directory not found!")
        return
    
    print("Checking Python file compilation...")
    
    # Find all Python files
    python_files = list(fastapi_dir.rglob("*.py"))
    
    compilation_errors = []
    import_errors = []
    
    for py_file in python_files:
        # Check compilation
        compiles, error = check_file_compilation(py_file)
        if not compiles:
            compilation_errors.append((py_file, error))
            print(f"❌ COMPILATION ERROR in {py_file}: {error}")
        else:
            print(f"✅ {py_file} compiles successfully")
    
    print(f"\n=== SUMMARY ===")
    print(f"Total files checked: {len(python_files)}")
    print(f"Compilation errors: {len(compilation_errors)}")
    
    if compilation_errors:
        print("\n=== COMPILATION ERRORS ===")
        for file_path, error in compilation_errors:
            print(f"{file_path}: {error}")
    else:
        print("✅ All files compile successfully!")

if __name__ == "__main__":
    main()
