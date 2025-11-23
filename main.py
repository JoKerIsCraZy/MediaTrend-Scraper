#!/usr/bin/env python3
"""
Media Top List Manager
An interactive tool to send top lists from streaming services
to Radarr and Sonarr.
"""

import sys
import settings
import worker
import utils.menu as menu

def show_main_menu():
    """Shows the main menu and waits for a selection."""
    print("\n=== Media Top List Manager (CLI Mode) ===")
    print("1) Run Top Lists Now")
    print("2) Manage Settings")
    print("3) Exit")
    return input("Choose an option: ").strip()

def run_cli():
    """Main loop of the CLI program."""
    
    # Load settings at startup
    config = settings.load_settings()

    while True:
        choice = show_main_menu()

        if choice == "1":
            # Starts the job execution menu
            worker.show_run_menu(config)
        
        elif choice == "2":
            # Starts the settings menu
            settings.show_settings_menu(config)
        
        elif choice == "3":
            print("Goodbye!")
            break
        
        else:
            menu.log_warn("Invalid selection, please try again.")

def main():
    if "--cli" in sys.argv:
        run_cli()
    else:
        # Start web server
        print("Starting Web Interface... (Use --cli for legacy mode)")
        from web.app import start_web_server
        start_web_server()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTerminated by user.")