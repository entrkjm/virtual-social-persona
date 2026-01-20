#!/usr/bin/env python3
"""
Cookie Management Script for Multi-Persona Twitter Bot Deployment.

Usage:
    python scripts/manage_cookies.py import <json_file> [--env-file <path>]
    python scripts/manage_cookies.py export [--env-file <path>]
    python scripts/manage_cookies.py show [--env-file <path>]

Examples:
    # Import cookies from browser export (EditThisCookie JSON format)
    python scripts/manage_cookies.py import cookies.json

    # Import to a specific persona's env file
    python scripts/manage_cookies.py import cookies.json --env-file personas/chef_choi/.env

    # Show current cookies from .env
    python scripts/manage_cookies.py show
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Default .env path
DEFAULT_ENV_PATH = Path(__file__).parent.parent / ".env"


def load_env_file(env_path: Path) -> dict:
    """Load .env file into a dictionary."""
    env_dict = {}
    if not env_path.exists():
        return env_dict
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                env_dict[key.strip()] = value.strip()
    return env_dict


def save_env_file(env_path: Path, env_dict: dict, original_lines: list):
    """Save dictionary back to .env file, preserving comments and order."""
    output_lines = []
    updated_keys = set()
    
    for line in original_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            output_lines.append(line)
            continue
        
        if '=' in stripped:
            key, _, _ = stripped.partition('=')
            key = key.strip()
            if key in env_dict:
                output_lines.append(f"{key}={env_dict[key]}\n")
                updated_keys.add(key)
            else:
                output_lines.append(line)
        else:
            output_lines.append(line)
    
    # Add new keys that weren't in original
    for key, value in env_dict.items():
        if key not in updated_keys:
            output_lines.append(f"{key}={value}\n")
    
    with open(env_path, 'w') as f:
        f.writelines(output_lines)


def import_cookies(json_path: str, env_path: Path):
    """
    Import cookies from JSON file (EditThisCookie export format).
    
    Expected JSON format:
    [
        {"name": "auth_token", "value": "xxx", ...},
        {"name": "ct0", "value": "yyy", ...},
        ...
    ]
    """
    with open(json_path, 'r') as f:
        cookies = json.load(f)
    
    auth_token = None
    ct0 = None
    
    for cookie in cookies:
        name = cookie.get('name', '')
        value = cookie.get('value', '')
        
        if name == 'auth_token':
            auth_token = value
        elif name == 'ct0':
            ct0 = value
    
    if not auth_token or not ct0:
        print("❌ Error: Could not find 'auth_token' or 'ct0' in the cookie file.")
        print("   Make sure you exported cookies from twitter.com")
        sys.exit(1)
    
    # Read original file
    original_lines = []
    if env_path.exists():
        with open(env_path, 'r') as f:
            original_lines = f.readlines()
    
    # Load and update
    env_dict = load_env_file(env_path)
    env_dict['TWITTER_AUTH_TOKEN'] = auth_token
    env_dict['TWITTER_CT0'] = ct0
    
    # Save
    save_env_file(env_path, env_dict, original_lines)
    
    print(f"✅ Cookies imported successfully to {env_path}")
    print(f"   auth_token: {auth_token[:10]}...{auth_token[-10:]}")
    print(f"   ct0: {ct0[:10]}...{ct0[-10:]}")
    print(f"\n   Updated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def export_cookies(env_path: Path):
    """Export current cookies to JSON (for backup or transfer)."""
    env_dict = load_env_file(env_path)
    
    auth_token = env_dict.get('TWITTER_AUTH_TOKEN')
    ct0 = env_dict.get('TWITTER_CT0')
    
    if not auth_token or not ct0:
        print(f"❌ No Twitter cookies found in {env_path}")
        sys.exit(1)
    
    output = [
        {"name": "auth_token", "value": auth_token, "domain": ".twitter.com"},
        {"name": "ct0", "value": ct0, "domain": ".twitter.com"}
    ]
    
    output_file = f"twitter_cookies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ Cookies exported to {output_file}")


def show_cookies(env_path: Path):
    """Display current cookie values."""
    env_dict = load_env_file(env_path)
    
    auth_token = env_dict.get('TWITTER_AUTH_TOKEN', '(not set)')
    ct0 = env_dict.get('TWITTER_CT0', '(not set)')
    
    print(f"📁 File: {env_path}")
    print(f"🔑 TWITTER_AUTH_TOKEN: {auth_token[:15]}...{auth_token[-10:] if len(auth_token) > 25 else auth_token}")
    print(f"🔑 TWITTER_CT0: {ct0[:15]}...{ct0[-10:] if len(ct0) > 25 else ct0}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage Twitter session cookies for bot deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Import from browser export:
    python scripts/manage_cookies.py import cookies.json

  Import for specific persona:
    python scripts/manage_cookies.py import cookies.json --env-file personas/chef_choi/.env

  Show current cookies:
    python scripts/manage_cookies.py show
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import cookies from JSON file')
    import_parser.add_argument('json_file', help='Path to JSON file (EditThisCookie export)')
    import_parser.add_argument('--env-file', type=Path, default=DEFAULT_ENV_PATH,
                               help=f'Path to .env file (default: {DEFAULT_ENV_PATH})')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export cookies to JSON file')
    export_parser.add_argument('--env-file', type=Path, default=DEFAULT_ENV_PATH,
                               help=f'Path to .env file (default: {DEFAULT_ENV_PATH})')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show current cookies')
    show_parser.add_argument('--env-file', type=Path, default=DEFAULT_ENV_PATH,
                             help=f'Path to .env file (default: {DEFAULT_ENV_PATH})')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'import':
        import_cookies(args.json_file, args.env_file)
    elif args.command == 'export':
        export_cookies(args.env_file)
    elif args.command == 'show':
        show_cookies(args.env_file)


if __name__ == '__main__':
    main()
