#!/usr/bin/env python3
"""
YouTube Clip Agent - Main Application Entry Point
"""
import sys
import os

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from gui.main_window import MainWindow
from utils.logging import setup_logging

def main():
    """Main application entry point"""
    setup_logging()
    app = MainWindow()
    app.run()

if __name__ == '__main__':
    main()
