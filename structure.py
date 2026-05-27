from pathlib import Path

# =========================================================
# CONFIG
# =========================================================

ROOT_DIR = r"./"   # Change this to your target folder

IGNORE = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".idea",
    ".vscode",
    "bin"
}


# =========================================================
# TREE PRINTING
# =========================================================

def print_tree(directory: Path, prefix: str = ""):
    items = sorted(
        [x for x in directory.iterdir() if x.name not in IGNORE],
        key=lambda x: (x.is_file(), x.name.lower())
    )

    pointers = ["├── "] * (len(items) - 1) + ["└── "]

    for pointer, item in zip(pointers, items):
        print(prefix + pointer + item.name)

        if item.is_dir():
            extension = "│   " if pointer == "├── " else "    "
            print_tree(item, prefix + extension)


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    root = Path(ROOT_DIR)

    print(root.resolve().name)
    print_tree(root)
