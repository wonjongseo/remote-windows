# windows_app_ui.py
# with using /Users/j_won/Desktop/projects/remote-windows/server/views/home.pug
# 1. cd server
# 2. npm run dev
# 3. open braswer and go to localhost:3000
# 4. enter any text

import sys
import asyncio
import json
from typing import Set, Dict

import cv2
import mss
import numpy as np
import pyautogui
import socketio
from av import VideoFrame
from qasync import QEventLoop, asyncSlot
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QComboBox, QPushButton,
    QLabel, QProgressBar, QLineEdit, QMessageBox
)
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCIceCandidate,
    VideoStreamTrack,
    RTCRtpSender,
)
from aiortc.sdp import candidate_from_sdp
import platform


MACOS = "Darwin"
class ScreenTrack(VideoStreamTrack):
    def __init__(self, monitor_idx: int, window, scale: int = 1, fps: int = 15):
        super().__init__()
        self.window = window
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[monitor_idx]
        self.scale = scale
        self.logical_w, self.logical_h = pyautogui.size()
        self._frame_interval = 1.0 / fps
        self._last_ts = None

    async def recv(self):
        now = asyncio.get_event_loop().time()
        if self._last_ts:
            wait = self._frame_interval - (now - self._last_ts)
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_ts = asyncio.get_event_loop().time()
        if not self.window.sharing_enabled:
            print("Screen sharing is disabled")
            raise asyncio.CancelledError()

        frame = self.sct.grab(self.monitor)
        arr = np.frombuffer(frame.rgb, dtype=np.uint8)
        arr = arr.reshape((frame.height, frame.width, 3))
        resized = cv2.resize(
            arr,
            (self.logical_w, self.logical_h),
            interpolation=cv2.INTER_LINEAR
        )
        vf = VideoFrame.from_ndarray(resized, format="rgb24")
        vf.pts, vf.time_base = await self.next_timestamp()
        return vf


async def run(monitor_idx: int, window):
    pc = RTCPeerConnection()
    sio = socketio.AsyncClient(reconnection=False)

    pc.addTrack(ScreenTrack(monitor_idx, window))

    dc = pc.createDataChannel("control")

    window.modifiers = set()

    @dc.on("message")
    def on_control(msg):
        print("Received msg:", msg)
        if not window.control_enabled:
            print("[DEBUG] control disabled")
            return

        cmd = json.loads(msg)
        typ = cmd.get("type")

        if typ == "key":
            key = cmd.get("key")
            event = cmd.get("event", "keydown")
            modifier_keys = {"Shift", "Control", "Alt", "Meta"}

            if key in modifier_keys:
                if event == "keydown":
                    window.modifiers.add(key.lower())
                else:  # "keyup"
                    window.modifiers.discard(key.lower())
                return

            arrow_map = {
                "ArrowUp": "up", "ArrowDown": "down", "ArrowLeft": "left", "ArrowRight": "right"
            }

            mapped = arrow_map.get(key, key.lower())

            if window.modifiers:
                mods = []
                for m in window.modifiers:
                    if m == "control":
                        # if platform.system() == "Darwin":
                        if platform.system() == MACOS:
                            mods.append("command")
                        else:
                            mods.append("ctrl")
                    elif m == "meta":
                        if platform.system() == MACOS:
                            mods.append("command")
                        else:
                            mods.append("ctrl")
                    else:
                        mods.append(m)

                # 押されているModifierを先にKeydown
                for k in mods:
                    pyautogui.keyDown(k)

                # 普通（？）のキーを押す。
                pyautogui.press(mapped)

                # 押されているModifierを解放する
                for k in mods:
                    pyautogui.keyUp(k)
            else:
                pyautogui.press(mapped)
            return
        
        # if typ == "click":
        if typ == "tap":
            sx = cmd.get("startX")
            sy = cmd.get("startY")
            ex = cmd.get("endX")
            ey = cmd.get("endY")

            # Click
            if sx == ex and sy == ey:
                pyautogui.click(x=sx, y=sy)
            else:
                # Drag
                pyautogui.mouseDown(x=sx, y=sy)
                pyautogui.moveTo(x=ex, y=ey)
                pyautogui.mouseUp(x=ex, y=ey)
            return

        if typ == "scroll":
            # sy = cmd.get("startY")
            # ey = cmd.get("endY")
            # delta = int((sy - ey))
            # pyautogui.scroll(delta)
            # return
            delta = cmd.get("deltaY", 0)
            pyautogui.scroll((delta))  # 브라우저 기준과 pyautogui는 반대 방향
            return

        if typ == "drag_start":
            pyautogui.mouseDown(x=cmd["x"], y=cmd["y"])
        elif typ == "drag_move":
            pyautogui.moveTo(x=cmd["x"], y=cmd["y"])
        elif typ == "drag_end":
            pyautogui.mouseUp(x=cmd["x"], y=cmd["y"])

    @sio.on("ice-candidate")
    async def on_remote_ice(data):
        if not data:
            return
        try:
            parsed = candidate_from_sdp(data["candidate"])
            ice = RTCIceCandidate(
                parsed.component,
                parsed.foundation,
                parsed.ip,
                parsed.port,
                parsed.priority,
                parsed.protocol,
                parsed.type,
                relatedAddress=parsed.relatedAddress,
                relatedPort=parsed.relatedPort,
                sdpMid=data["sdpMid"],
                sdpMLineIndex=data["sdpMLineIndex"],
                tcpType=parsed.tcpType
            )
            await pc.addIceCandidate(ice)

        except Exception as e:
            print(f"[Error: {e!r}]")
            raise

    @sio.event
    async def connect():
        window.progress.hide()
        window.update_status("接続済み")

        print("🔌 Connected Signaling Server")
        
        video_caps = RTCRtpSender.getCapabilities("video").codecs

        preferred = []
        for codec in video_caps:
            if codec.mimeType == "video/VP8":
                codec.parameters["x-google-min-bitrate"] = 200  # int
                codec.parameters["x-google-max-bitrate"] = 800  # int
                preferred.append(codec)

        for transceiver in pc.getTransceivers():
            if transceiver.kind == "video":
                transceiver.setCodecPreferences(preferred)


        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        await sio.emit("sdp", {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })
        print("🔌 sdp(offer) to Signaling")


    @sio.on("sdp")
    async def on_sdp(data):
        print("📝 Get sdp", data["type"])
        if data["type"] != "answer":
            return

        if pc.signalingState != "have-local-offer":
            print(f"[警告] signalingState={pc.signalingState}, answer 無視")
            return

        answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        await pc.setRemoteDescription(answer)


    @sio.event
    async def disconnect():
        # 연결 해제 시 PeerConnection 닫기
        print("[DEBUG] socket is disconnected")
        window.update_status("待機切断")
        await pc.close()

    # Signaling 서버 연결
    # await sio.connect("http://localhost:3000")
    server_url = window.ip_input.text().strip()
    try:
        await sio.connect(server_url, transports=["websocket"])
    except Exception as e:
        QMessageBox.critical(window, "接続エラー", f"{server_url}に接続できませんでした: {e}")
        return
    await sio.wait()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Windows Remote Application")

        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.show()

        self.sharing_enabled = False
        self.control_enabled = False

        self.monitors = mss.mss().monitors  # index == 0 全体, 1~Nは個別モニター
        self._init_ui()

    def update_status(self, text: str):
        self.lbl_status.setText(f"状態: {text}")
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        top_layout = QHBoxLayout()

        self.lbl_status = QLabel("状態：接続前")
        top_layout.addWidget(self.lbl_status)

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("http://<SERVER_IP>:3000")
        self.ip_input.setText("http://localhost:3000")
        top_layout.addWidget(self.ip_input)

        self.combo = QComboBox()
        for idx, mon in enumerate(self.monitors):
            txt = f"Monitor {idx}: {mon['width']}×{mon['height']}"
            self.combo.addItem(txt, userData=idx)
        top_layout.addWidget(self.combo)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)         
        self.progress.hide()
        top_layout.addWidget(self.progress)

        self.btn_permission = QPushButton("リモート操作")
        self.btn_permission.clicked.connect(self.on_click_permission)
        top_layout.addWidget(self.btn_permission)

        self.btn_toggle_control = QPushButton("リモート制御　オフ")
        self.btn_toggle_control.clicked.connect(self.on_click_toggle_control)
        self.btn_toggle_control.hide()

        self.btn_stop_sharing = QPushButton("画面共有　オフ")
        self.btn_stop_sharing.clicked.connect(self.on_click_stop_sharing)
        self.btn_stop_sharing.hide()

        top_layout.addWidget(self.btn_toggle_control)
        top_layout.addWidget(self.btn_stop_sharing)

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        central.setLayout(main_layout)

    @asyncSlot()
    async def on_click_permission(self):
        idx = self.combo.currentData()

        self.progress.show()
        self.update_status("接続中。。。")
        self.sharing_enabled = True
        self.control_enabled = True

        self.btn_permission.hide()
        self.btn_toggle_control.show()
        self.btn_stop_sharing.show()

        await asyncio.sleep(0.1)
        asyncio.create_task(run(idx, self))  

    def on_click_toggle_control(self):
        self.control_enabled = not self.control_enabled

        if self.control_enabled:
            self.btn_toggle_control.setText("リモート操作　オフ")
        else:
            self.btn_toggle_control.setText("リモート操作　オン")

    def on_click_stop_sharing(self):
        if not self.sharing_enabled:
            return
        
        self.sharing_enabled = False
        self.control_enabled = False

        self.btn_toggle_control.hide()
        self.btn_stop_sharing.hide()
        self.btn_permission.show()

        self.update_status("待機中")

def main():
    app = QApplication(sys.argv)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    win = MainWindow()
    win.resize(700, 1)
    win.show()

    screen = app.primaryScreen()
    geo = screen.availableGeometry()  

    frame_geo = win.frameGeometry()

    x = geo.x() + (geo.width()  - frame_geo.width())  // 2
    y = geo.y()

    win.move(QPoint(x, y))
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()


