from pathlib import Path


def workspace_root() -> Path:
    """Return the writable project workspace for local and Render Docker runtimes."""
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if (parent / "scripts" / "validate_products_csv.py").exists():
            return parent
    for parent in current_file.parents:
        if (parent / "pyproject.toml").exists() and (parent / "app").is_dir():
            return parent
    return Path.cwd()
