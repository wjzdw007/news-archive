#!/usr/bin/env python3
"""Validate static site structure and data integrity."""

import json
import sys
from pathlib import Path


def validate_json_file(filepath: Path, expected_keys: list[str]) -> tuple[bool, str]:
    """Validate JSON file exists and has expected structure."""
    if not filepath.exists():
        return False, f"Missing: {filepath}"
    
    try:
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            return False, f"{filepath.name} must be an array"
        
        if data and expected_keys:
            first_item = data[0]
            missing_keys = [k for k in expected_keys if k not in first_item]
            if missing_keys:
                return False, f"{filepath.name} items missing keys: {missing_keys}"
            if filepath.name == "articles.json" and "content_snapshot" in first_item:
                return False, "articles.json must not include content_snapshot"
            if filepath.name == "daily_briefs.json" and "content_snapshot" in first_item:
                return False, "daily_briefs.json must not include content_snapshot"
            if filepath.name == "x_posts.json":
                allowed = {
                    "author",
                    "posted_at",
                    "fetched_at",
                    "text_snapshot",
                    "url",
                    "status",
                }
                extra = set(first_item) - allowed
                if extra:
                    return False, f"x_posts.json has non-display keys: {sorted(extra)}"
        
        return True, f"✓ {filepath.name}: {len(data)} items"
        
    except json.JSONDecodeError as e:
        return False, f"{filepath.name} invalid JSON: {e}"
    except Exception as e:
        return False, f"{filepath.name} error: {e}"


def validate_html_file(filepath: Path) -> tuple[bool, str]:
    """Validate HTML file exists and has basic structure."""
    if not filepath.exists():
        return False, f"Missing: {filepath}"
    
    content = filepath.read_text(encoding="utf-8")
    
    required_elements = [
        "<!DOCTYPE html>",
        "<html",
        "<head>",
        "<body>",
        "新闻",  # News tab
        "专题",  # Topics tab
        "X",     # X tab
        "日报",  # Daily brief tab
    ]
    
    missing = [elem for elem in required_elements if elem not in content]
    if missing:
        return False, f"index.html missing elements: {missing}"
    
    return True, f"✓ index.html: {len(content)} bytes"


def main() -> int:
    site_dir = Path("site")
    data_dir = site_dir / "data"
    
    print("Validating static site structure...\n")
    
    # Validate data JSON files
    validations = [
        (data_dir / "articles.json", ["url", "title", "source", "fetched_at"]),
        (data_dir / "topics.json", ["topic_id", "title", "sources", "status"]),
        (data_dir / "x_posts.json", ["author", "posted_at", "fetched_at", "text_snapshot", "url", "status"]),
        (data_dir / "daily_briefs.json", ["date", "generated_at", "status", "model", "lede", "sections"]),
    ]
    
    all_passed = True
    for filepath, expected_keys in validations:
        passed, message = validate_json_file(filepath, expected_keys)
        print(message)
        all_passed = all_passed and passed
    
    print()
    
    # Validate HTML files
    html_files = [
        site_dir / "index.html",
        site_dir / "app.js",
        site_dir / "style.css",
        site_dir / "favicon.svg",
    ]
    
    for filepath in html_files:
        if filepath.suffix == ".html":
            passed, message = validate_html_file(filepath)
        else:
            passed = filepath.exists()
            message = f"✓ {filepath.name}: {len(filepath.read_text()) if passed else 0} bytes"
        
        print(message)
        all_passed = all_passed and passed
    
    print()
    
    if all_passed:
        print("✅ All validations passed")
        return 0
    else:
        print("❌ Some validations failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
