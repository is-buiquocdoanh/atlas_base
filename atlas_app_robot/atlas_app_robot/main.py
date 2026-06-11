#!/usr/bin/env python3
"""Entry point for atlas_app_robot — touchscreen app running on the robot."""
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description='Atlas Robot Touchscreen App')
    parser.add_argument('--host', default='localhost:8080',
                        help='Atlas API host:port (default: localhost:8080)')
    parser.add_argument('--fullscreen', action='store_true',
                        help='Launch in fullscreen mode (for embedded display)')
    args, _ = parser.parse_known_args()

    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    from .robot_window import RobotAppWindow
    win = RobotAppWindow(host=args.host)

    if args.fullscreen:
        win.showFullScreen()
    else:
        win.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
