
import sys
import threading
import asyncio
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot

from webrtc_client import WebRTCClient

class SignalBridge(QObject):
    status = pyqtSignal(str)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Remote Control UI")
        layout = QVBoxLayout()

        self.status_label = QLabel("■ 상태: 대기중")
        layout.addWidget(self.status_label)

        self.start_btn = QPushButton("▶ 연결 시작")
        self.start_btn.clicked.connect(self.start)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("■ 연결 중지")
        self.stop_btn.clicked.connect(self.stop)
        layout.addWidget(self.stop_btn)

        self.setLayout(layout)

        # status bridge
        self.bridge = SignalBridge()
        self.bridge.status.connect(self.update_status)

        # WebRTC client and loop
        self.client = WebRTCClient()
        self.loop = asyncio.new_event_loop()

    @pyqtSlot()
    def start(self):
        threading.Thread(target=self._run_client, daemon=True).start()
        self.bridge.status.emit("연결 대기중...")

    def _run_client(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.client.run())

    @pyqtSlot()
    def stop(self):
        asyncio.run_coroutine_threadsafe(self.client.shutdown(), self.loop)
        self.bridge.status.emit("연결 중지됨")

    @pyqtSlot(str)
    def update_status(self, text):
        self.status_label.setText(f"■ 상태: {text}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
