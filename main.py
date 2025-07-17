# windows_app_ui.py
# with using /Users/j_won/Desktop/projects/remote-windows/server/views/home.pug
# 1. cd server
# 2. npm run dev
# 3. open braswer and go to localhost:3000
# 4. enter any text

import sys
import asyncio
import mss
import pyautogui

from qasync import QEventLoop, asyncSlot
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QComboBox, QPushButton,
    QLabel, QProgressBar
)
from PyQt5.QtCore import QPoint, Qt
import asyncio
import json
import mss
import numpy as np
import pyautogui
import socketio
import cv2



from aiortc.sdp import candidate_from_sdp
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCIceCandidate,
    VideoStreamTrack,
)
from av import VideoFrame

import asyncio
import json
import mss
import numpy as np
import pyautogui
import socketio
import cv2

from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCIceCandidate,
    VideoStreamTrack,
)
from av import VideoFrame

async def run(monitor_idx: int, window):
    """
    monitor_idx: QComboBox에서 선택한 모니터 인덱스
    window: MainWindow 인스턴스 (sharing_enabled, control_enabled 속성 사용)
    """
    # WebRTC peer
    pc = RTCPeerConnection()
    sio = socketio.AsyncClient()

    # 커스텀 ScreenTrack: 선택된 모니터로 캡처
    class ScreenTrack(VideoStreamTrack):
        def __init__(self, scale=1):
            super().__init__()
            self.sct = mss.mss()
            self.monitor = self.sct.monitors[monitor_idx]
            # self.monitor = self.sct.monitors[1]
            self.scale = scale
            self.logical_w, self.logical_h = pyautogui.size()

        async def recv(self):
            # 화면 공유 중이 아닐 땐 취소
            if not window.sharing_enabled:
                print("[ScreenTrack] 공유 꺼짐, Cancelled")
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

    pc.addTrack(ScreenTrack())

    # 데이터 채널(control) 핸들러
    dc = pc.createDataChannel("control")
    # 조합키 상태 저장
    window.modifiers = set()
    @dc.on("message")
    def on_control(msg):
        print("[DEBUG] on_control received:", msg)
        
        if not window.control_enabled:
            print("[DEBUG] control disabled")
            return
        cmd = json.loads(msg)
        typ = cmd.get("type")
        x = cmd.get("x")
        y = cmd.get("y")
        # 키 입력 처리 (단일키 & 조합키)
        if typ == "key":
            key = cmd.get("key")
            modifier_keys = {"Shift", "Control", "Alt", "Meta"}
            if key in modifier_keys:
                # modifier 로 저장
                window.modifiers.add(key.lower())
                return
            # 방향키 매핑
            arrow_map = {
                "ArrowUp": "up",
                "ArrowDown": "down",
                "ArrowLeft": "left",
                "ArrowRight": "right"
            }
            mapped_key = arrow_map.get(key, key.lower())
            if window.modifiers:
                # pyautogui.hotkey expects 'ctrl' not 'control'
                mods = []
                for m in window.modifiers:
                    if m == 'control': mods.append('ctrl')
                    elif m == 'meta': mods.append('command')
                    else: mods.append(m)

                print("mods: ", mods  )
                pyautogui.hotkey(*mods, mapped_key)
                window.modifiers.clear()
            else:
                pyautogui.press(mapped_key)
            return
        # 마우스 드래그 처리
        if typ == "drag_start":
            pyautogui.mouseDown(x, y)
            return
        elif typ == "drag_move":
            pyautogui.moveTo(x, y)
            return
        elif typ == "drag_end":
            pyautogui.mouseUp(x, y)
            return
        # 클릭
        if typ == "mouse":
            pyautogui.moveTo(x, y)
            if cmd.get("click"):
                pyautogui.click()
            return
        # 휠
        if typ == "wheel":
            delta = cmd.get("delta", 0)
            pyautogui.scroll(delta)
            return

    @sio.on("ice-candidate")
    async def on_remote_ice(data):
        print(data)
        if not data:
            return
        try:
            # 1) SDP 문자열(candidate:...) → RTCIceCandidate (with component, ip, port, ...)
            parsed = candidate_from_sdp(data["candidate"])
            # 2) sdpMid, sdpMLineIndex 정보만 덧붙여 실제 객체 생성
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
            # 3) 피어 커넥션에 추가
            await pc.addIceCandidate(ice)

        except Exception as e:
            print(f"[오류 발생: {e!r}]")
            raise

     # 시그널링 이벤트들 정의
    @sio.event
    async def connect():
                # 연결 성공 시 프로그래스 바 숨기고 상태 갱신
        window.progress.hide()
        window.update_status("연결됨")

        print("🔌 Connected Signaling Server")
        # 방에 참가
        
        # Offer 생성 & 전송
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

        # 이미 remoteDescription이 설정됐거나 offer 상태가 아니면 무시
        if pc.signalingState != "have-local-offer":
            print(f"[경고] signalingState={pc.signalingState}, answer 무시")
            return

        answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        await pc.setRemoteDescription(answer)


    @sio.event
    async def disconnect():
        # 연결 해제 시 PeerConnection 닫기
        window.update_status("대기중")
        await pc.close()

    # Signaling 서버 연결
    await sio.connect("http://localhost:3000")
    await sio.wait()




class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("원격 제어 애플리케이션")

        # ─── 윈도우를 항상 위에 표시 ───
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        # 변경한 플래그가 반영되도록
        self.show()
        # ───────────────────────────────

        # 공유/제어 상태 플래그
        self.sharing_enabled = False
        self.control_enabled = False

        # mss로 모니터 리스트 가져오기
        self.monitors = mss.mss().monitors  # index 0은 전체, 1~N이 개별 모니터
        

        # UI 구성
        self._init_ui()
    def update_status(self, text: str):
        """상단 상태 레이블 텍스트 갱신"""
        self.lbl_status.setText(f"상태: {text}")
    def _init_ui(self):
        # 중앙 위젯
        central = QWidget()
        self.setCentralWidget(central)

        # 상단 레이아웃: 드롭다운 + 버튼
        top_layout = QHBoxLayout()

        # 상태 표시 레이블
        self.lbl_status = QLabel("상태: 대기중")
        top_layout.addWidget(self.lbl_status)

        # 모니터 선택 드롭다운
        self.combo = QComboBox()
        for idx, mon in enumerate(self.monitors):
            # 예: Monitor 1: 1920×1080
            txt = f"Monitor {idx}: {mon['width']}×{mon['height']}"
            self.combo.addItem(txt, userData=idx)
        top_layout.addWidget(self.combo)

                # 프로그래스 바 (숨김 상태, indeterminate 모드)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)         # 0,0 → indeterminate
        self.progress.hide()
        top_layout.addWidget(self.progress)

        # 버튼: 처음엔 허가 버튼만
        self.btn_permission = QPushButton("원격 제어 허가")
        self.btn_permission.clicked.connect(self.on_click_permission)
        top_layout.addWidget(self.btn_permission)

        # 나중에 나올 버튼들
        self.btn_toggle_control = QPushButton("원격 제어 끄기 (Ctrl+P)")
        self.btn_toggle_control.clicked.connect(self.on_click_toggle_control)
        self.btn_toggle_control.hide()

        self.btn_stop_sharing = QPushButton("화면 공유 끄기")
        self.btn_stop_sharing.clicked.connect(self.on_click_stop_sharing)
        self.btn_stop_sharing.hide()

        top_layout.addWidget(self.btn_toggle_control)
        top_layout.addWidget(self.btn_stop_sharing)

        # 전체 레이아웃
        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        central.setLayout(main_layout)

    @asyncSlot()
    async def on_click_permission(self):
        """원격 제어 허가"""
        # 1) 선택된 모니터 인덱스
        idx = self.combo.currentData()
        print(f"[UI] 선택된 모니터: {idx}")

        self.progress.show()
        self.update_status("연결 중…")
        # 2) 공유 + 제어 모드 시작
        self.sharing_enabled = True
        self.control_enabled = True

        # 버튼 토글
        self.btn_permission.hide()
        self.btn_toggle_control.show()
        self.btn_stop_sharing.show()

        # TODO: 실제 WebRTC run 코루틴을 여기에 띄우세요.
        # 예) 
        await asyncio.sleep(0.1)
        asyncio.create_task(run(idx, self))  
        # run 함수 내부에서 self.sharing_enabled, self.control_enabled 를 확인하며 동작하도록 수정 필요

    def on_click_toggle_control(self):
        """control_enabled 값을 토글하고, 버튼 텍스트 갱신"""
        # 상태 토글
        self.control_enabled = not self.control_enabled

        # 텍스트 변경
        if self.control_enabled:
            self.btn_toggle_control.setText("원격 제어 비활성화")
            print("[UI] 원격 제어 ON")
        else:
            self.btn_toggle_control.setText("원격 제어 활성화")
            print("[UI] 원격 제어 OFF")

    def on_click_stop_sharing(self):
        """화면 공유 & 제어 모두 끄기"""
        if not self.sharing_enabled:
            return
        
        self.sharing_enabled = False
        self.control_enabled = False
        print("[UI] 화면 공유 및 원격 제어 모두 OFF")

        # UI 원상복귀
        self.btn_toggle_control.hide()
        self.btn_stop_sharing.hide()
        self.btn_permission.show()


        self.update_status("대기중")

        # TODO: WebRTC connection close / cleanup 로직 호출

def main():
    app = QApplication(sys.argv)

    # qasync로 asyncio 이벤트루프 통합
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    win = MainWindow()
    win.resize(600, 1)
    win.show()

    # ─── 화면 상단 중앙으로 이동 ───
    # 1) 화면(모니터) 정보를 가져옴
    screen = app.primaryScreen()
    geo = screen.availableGeometry()  # 작업 표시줄 등을 제외한 사용 가능한 영역

    # 2) 윈도우 전체 프레임(툴바, 테두리 포함) 크기 정보
    frame_geo = win.frameGeometry()

    # 3) X좌표: 화면 왼쪽 + (화면 너비/2) – (윈도우 너비/2)
    x = geo.x() + (geo.width()  - frame_geo.width())  // 2
    # Y좌표: 화면 최상단
    y = geo.y()

    # 4) 이동
    win.move(QPoint(x, y))
    # ─────────────────────────────

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()


