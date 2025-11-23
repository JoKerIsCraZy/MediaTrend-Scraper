#!/usr/bin/env python3
import sys
from typing import Any, List, Optional, Dict

def log(msg: str) -> None:
    """Eine einfache Logging-Funktion."""
    print(f"[INFO] {msg}", flush=True)

def log_warn(msg: str) -> None:
    """Eine Logging-Funktion für Warnungen."""
    print(f"[WARN] {msg}", flush=True)

def log_error(msg: str) -> None:
    """Eine Logging-Funktion für Fehler."""
    print(f"[ERROR] {msg}", flush=True)

def prompt(msg: str, default: Optional[str] = None) -> str:
    """Fragt den Benutzer nach einer Eingabe."""
    if default is not None:
        txt = input(f"{msg} [{default}]: ").strip()
        return txt if txt else default
    return input(f"{msg}: ").strip()

def prompt_yes_no(msg: str, default: bool = False) -> bool:
    """Fragt nach einer Ja/Nein-Entscheidung."""
    hint = "Y/n" if default else "y/N"
    ans = input(f"{msg} ({hint}): ").strip().lower()
    if not ans:
        return default
    return ans.startswith("y") or ans == "ja"

def prompt_for_selection(
    title: str,
    items: List[Dict[str, Any]],
    display_key: str,
    current_value: Any,
    value_key: str,
    allow_multi: bool = False
) -> Optional[Any]:
    """
    Zeigt eine nummerierte Liste von Elementen (z.B. Profile, Ordner, Länder) zur Auswahl an.
    
    Args:
        title: Die Überschrift für das Menü (z.B. "--- Radarr-Qualitätsprofile ---")
        items: Eine Liste von Dictionaries (z.B. [{'name': 'HD-1080p', 'id': 1}, ...])
        display_key: Der Schlüssel, der für die Anzeige verwendet wird (z.B. 'name')
        current_value: Der aktuell gespeicherte Wert (z.B. 1 oder ['US', 'DE'])
        value_key: Der Schlüssel, dessen Wert zurückgegeben werden soll (z.B. 'id')
        allow_multi: Ob Mehrfachauswahl (Komma-getrennt) erlaubt ist.

    Returns:
        Der ausgewählte Wert (z.B. 1) oder eine Liste von Werten (z.B. ['US', 'DE']).
    """
    print(f"\n{title}")
    print("-" * len(title))

    if not items:
        log_warn("Keine Elemente zur Auswahl verfügbar.")
        return None

    default_idx_str = ""
    is_list = isinstance(current_value, list)

    for i, item in enumerate(items):
        name = item.get(display_key, 'N/A')
        value = item.get(value_key)
        current_mark = ""

        if is_list:
            if value in current_value:
                current_mark = " <-- Aktuell"
        elif value == current_value:
            current_mark = " <-- Aktuell"
            default_idx_str = str(i + 1)
        
        print(f"{i+1}) {name}{current_mark}")

    if allow_multi:
        print("\nMehrfachauswahl mit Komma trennen (z.B. 1, 3, 5).")
        print("Für 'Global' (alle): 'all'")
        if is_list:
            # Zeigt die aktuellen Indizes als Standard an
            default_indices = [str(i+1) for i, item in enumerate(items) if item.get(value_key) in current_value]
            default_idx_str = ", ".join(default_indices)

    try:
        choice_str = prompt(f"Auswahl (1-{len(items)}) treffen", default_idx_str)

        if not choice_str:
            return current_value # Keine Änderung

        if allow_multi:
            if choice_str.lower() == 'all':
                return [item[value_key] for item in items] # Alle zurückgeben
            
            selected_values = []
            indices = [int(x.strip()) - 1 for x in choice_str.split(',')]
            for idx in indices:
                if 0 <= idx < len(items):
                    selected_values.append(items[idx][value_key])
            return selected_values
        
        else: # Einzelauswahl
            choice_idx = int(choice_str) - 1
            if 0 <= choice_idx < len(items):
                return items[choice_idx][value_key]
            else:
                log_warn("Ungültige Auswahl. Aktueller Wert wird beibehalten.")
                return current_value

    except ValueError:
        log_warn("Ungültige Eingabe. Aktueller Wert wird beibehalten.")
        return current_value
    except Exception as e:
        log_error(f"Fehler bei der Auswahl: {e}")
        return current_value