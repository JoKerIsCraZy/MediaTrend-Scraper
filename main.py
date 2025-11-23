#!/usr/bin/env python3
"""
Media-Top-Listen-Manager
Ein interaktives Tool, um Top-Listen von Streaming-Diensten 
an Radarr und Sonarr zu senden.
"""

import sys
import settings
import worker
import utils.menu as menu

def show_main_menu():
    """Zeigt das Hauptmenü an und wartet auf eine Auswahl."""
    print("\n=== Media-Top-Listen-Manager (CLI Modus) ===")
    print("1) Top-Listen jetzt ausführen")
    print("2) Einstellungen verwalten")
    print("3) Beenden")
    return input("Wählen Sie eine Option: ").strip()

def run_cli():
    """Haupt-Loop des CLI-Programms."""
    
    # Lädt die Einstellungen beim Start
    config = settings.load_settings()

    while True:
        choice = show_main_menu()

        if choice == "1":
            # Startet das Job-Ausführungs-Menü
            worker.show_run_menu(config)
        
        elif choice == "2":
            # Startet das Einstellungs-Menü
            settings.show_settings_menu(config)
        
        elif choice == "3":
            print("Auf Wiedersehen!")
            break
        
        else:
            menu.log_warn("Ungültige Auswahl, bitte erneut versuchen.")

def main():
    if "--cli" in sys.argv:
        run_cli()
    else:
        # Webserver starten
        print("Starte Web-Interface... (Verwende --cli für den alten Modus)")
        from web.app import start_web_server
        start_web_server()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBeendet durch Benutzer.")