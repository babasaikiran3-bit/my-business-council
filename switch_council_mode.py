#!/usr/bin/env python3
"""Switch between standard council and ADD-enabled council implementations."""

import sys
import shutil
import os

def switch_to_add_mode():
    """Switch to ADD-enabled council implementation."""
    backend_path = "./llm-council/backend/"
    
    # Backup original council.py if not already done
    if not os.path.exists(f"{backend_path}council_original.py"):
        shutil.copy(f"{backend_path}council.py", f"{backend_path}council_original.py")
        print("✓ Backed up original council.py to council_original.py")
    
    # Copy ADD-enabled version
    shutil.copy(f"{backend_path}council_add.py", f"{backend_path}council.py")
    print("✓ Switched to ADD-enabled council implementation")
    
    # Import and show current mode
    sys.path.append('./llm-council')
    from backend import council
    print(f"  Current ADD mode: {council.ADD_FRAMEWORK_MODE}")
    print("\nTo change ADD mode, edit ADD_FRAMEWORK_MODE in council.py")
    print("Options: 'none', 'all', 'chairman_only', 'council_only'")


def switch_to_standard_mode():
    """Switch back to standard council implementation."""
    backend_path = "./llm-council/backend/"
    
    if os.path.exists(f"{backend_path}council_original.py"):
        shutil.copy(f"{backend_path}council_original.py", f"{backend_path}council.py")
        print("✓ Switched back to standard council implementation")
    else:
        print("⚠ No backup found. Current council.py may already be standard.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ['add', 'standard']:
        print("Usage: python switch_council_mode.py [add|standard]")
        print("  add      - Switch to ADD-enabled council")
        print("  standard - Switch to standard council")
        sys.exit(1)
    
    if sys.argv[1] == 'add':
        switch_to_add_mode()
    else:
        switch_to_standard_mode()