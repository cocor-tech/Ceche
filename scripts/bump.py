#!/usr/bin/env python3
"""Bump the version in pyproject.toml. Usage: python scripts/bump.py [patch|minor|major]"""

import re
import sys
from pathlib import Path


def bump(part: str) -> None:
    path = Path("pyproject.toml")
    content = path.read_text()
    match = re.search(r'version = "(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        print("Version not found in pyproject.toml")
        sys.exit(1)

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1
    else:
        print("Usage: bump.py [patch|minor|major]")
        sys.exit(1)

    new_ver = f"{major}.{minor}.{patch}"
    content = content.replace(f'version = "{match.group(0)}"', f'version = "{new_ver}"')
    path.write_text(content)
    print(f"Bumped to {new_ver}")


if __name__ == "__main__":
    bump(sys.argv[1] if len(sys.argv) > 1 else "patch")
