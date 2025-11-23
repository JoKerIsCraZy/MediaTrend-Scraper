#!/usr/bin/env python3
import sys
from typing import Any, List, Optional, Dict

def log(msg: str) -> None:
    """A simple logging function."""
    print(f"[INFO] {msg}", flush=True)

def log_warn(msg: str) -> None:
    """A logging function for warnings."""
    print(f"[WARN] {msg}", flush=True)

def log_error(msg: str) -> None:
    """A logging function for errors."""
    print(f"[ERROR] {msg}", flush=True)

def prompt(msg: str, default: Optional[str] = None) -> str:
    """Asks the user for input."""
    if default is not None:
        txt = input(f"{msg} [{default}]: ").strip()
        return txt if txt else default
    return input(f"{msg}: ").strip()

def prompt_yes_no(msg: str, default: bool = False) -> bool:
    """Asks for a Yes/No decision."""
    hint = "Y/n" if default else "y/N"
    ans = input(f"{msg} ({hint}): ").strip().lower()
    if not ans:
        return default
    return ans.startswith("y") or ans == "yes"

def prompt_for_selection(
    title: str,
    items: List[Dict[str, Any]],
    display_key: str,
    current_value: Any,
    value_key: str,
    allow_multi: bool = False
) -> Optional[Any]:
    """
    Displays a numbered list of items (e.g., profiles, folders, countries) for selection.
    
    Args:
        title: The title for the menu (e.g., "--- Radarr Quality Profiles ---")
        items: A list of dictionaries (e.g., [{'name': 'HD-1080p', 'id': 1}, ...])
        display_key: The key used for display (e.g., 'name')
        current_value: The currently stored value (e.g., 1 or ['US', 'DE'])
        value_key: The key whose value should be returned (e.g., 'id')
        allow_multi: Whether multiple selection (comma-separated) is allowed.

    Returns:
        The selected value (e.g., 1) or a list of values (e.g., ['US', 'DE']).
    """
    print(f"\n{title}")
    print("-" * len(title))

    if not items:
        log_warn("No items available for selection.")
        return None

    default_idx_str = ""
    is_list = isinstance(current_value, list)

    for i, item in enumerate(items):
        name = item.get(display_key, 'N/A')
        value = item.get(value_key)
        current_mark = ""

        if is_list:
            if value in current_value:
                current_mark = " <-- Current"
        elif value == current_value:
            current_mark = " <-- Current"
            default_idx_str = str(i + 1)
        
        print(f"{i+1}) {name}{current_mark}")

    if allow_multi:
        print("\nSeparate multiple selections with commas (e.g., 1, 3, 5).")
        print("For 'Global' (all): 'all'")
        if is_list:
            # Shows current indices as default
            default_indices = [str(i+1) for i, item in enumerate(items) if item.get(value_key) in current_value]
            default_idx_str = ", ".join(default_indices)

    try:
        choice_str = prompt(f"Make selection (1-{len(items)})", default_idx_str)

        if not choice_str:
            return current_value # No change

        if allow_multi:
            if choice_str.lower() == 'all':
                return [item[value_key] for item in items] # Return all
            
            selected_values = []
            indices = [int(x.strip()) - 1 for x in choice_str.split(',')]
            for idx in indices:
                if 0 <= idx < len(items):
                    selected_values.append(items[idx][value_key])
            return selected_values
        
        else: # Single selection
            choice_idx = int(choice_str) - 1
            if 0 <= choice_idx < len(items):
                return items[choice_idx][value_key]
            else:
                log_warn("Invalid selection. Keeping current value.")
                return current_value

    except ValueError:
        log_warn("Invalid input. Keeping current value.")
        return current_value
    except Exception as e:
        log_error(f"Error during selection: {e}")
        return current_value