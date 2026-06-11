import sys
import threading

import rclpy
from PyQt5.QtWidgets import QApplication

from .node import AtlasNode
from .main_window import AtlasAppWindow


def main():
    rclpy.init(args=sys.argv)
    node = AtlasNode()

    # spin ROS2 in a background daemon thread
    ros_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    ros_thread.start()

    app = QApplication(sys.argv)
    app.setApplicationName('Atlas App')

    window = AtlasAppWindow(node)
    window.show()
    window.map_widget.fit_map()

    exit_code = app.exec_()

    node.destroy_node()
    rclpy.shutdown()
    sys.exit(exit_code)
