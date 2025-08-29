#!/usr/bin/env python3
"""
Script to manually fix YAML formatting issues in MongoDB production manifest
"""


def fix_yaml_manual(file_path):
    """Manually fix YAML formatting issues."""

    with open(file_path) as f:
        lines = f.readlines()

    # Fix the specific lines that have formatting issues
    fixed_lines = []
    for _i, line in enumerate(lines):
        if line.strip() == "key: BINANCE_API_SECRET            - name: MONGODB_URI":
            # Split this into two lines
            fixed_lines.append("                  key: BINANCE_API_SECRET\n")
            fixed_lines.append("            - name: MONGODB_URI\n")
        else:
            fixed_lines.append(line)

    # Write the fixed content back
    with open(file_path, "w") as f:
        f.writelines(fixed_lines)

    print(f"✅ Manually fixed YAML formatting in {file_path}")


def main():
    """Main function to fix YAML formatting."""

    files_to_fix = ["k8s/klines-mongodb-production.yaml"]

    for file_path in files_to_fix:
        if os.path.exists(file_path):
            fix_yaml_manual(file_path)
        else:
            print(f"❌ File not found: {file_path}")

    print("🎉 YAML formatting manually fixed!")


if __name__ == "__main__":
    import os

    main()
