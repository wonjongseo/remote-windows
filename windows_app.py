# windows_app.py
import cv2
import asyncio
import json
import mss
import numpy as np
import pyautogui
import socketio

from aiortc.sdp import candidate_from_sdp


from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
    RTCIceCandidate,    
)
from av import VideoFrame

# 1) 시그널링 클라이언트 설정
sio = socketio.AsyncClient()


# 2) 화면 캡처용 VideoStreamTrack
class ScreenTrack(VideoStreamTrack):
    def __init__(self,scale=1):
        super().__init__()  
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]  # 전체 화면
        self.scale = scale
        self.logical_w, self.logical_h = pyautogui.size()

    async def recv(self):
        try:
            ###
            # Windows
                # 1) 화면 캡처
            # frame = self.sct.grab(self.monitor)

            # # 2) raw bytes → uint8 배열 → (height, width, 3) 형태로 재배치
            # arr = np.frombuffer(frame.rgb, dtype=np.uint8)
            # arr = arr.reshape((frame.height, frame.width, 3))

            # # 3) VideoFrame 생성
            # vf = VideoFrame.from_ndarray(arr, format="rgb24")
            # vf.pts, vf.time_base = await self.next_timestamp()
            # return vf
            ###

            #Mac
            frame = self.sct.grab(self.monitor)
            arr = np.frombuffer(frame.rgb, dtype=np.uint8)
            arr = arr.reshape((frame.height, frame.width, 3))

            # 물리 → 논리 해상도로 리사이즈
            resized = cv2.resize(
                arr,
                (self.logical_w, self.logical_h),
                interpolation=cv2.INTER_LINEAR
            )

            vf = VideoFrame.from_ndarray(resized, format="rgb24")
            vf.pts, vf.time_base = await self.next_timestamp()
            return vf

        except Exception as e:
            print(f"[ScreenTrack.recv] 오류 발생: {e!r}")
            # 예외를 다시 던지거나 None 반환
            raise

async def run():
    # WebRTC 피어 연결 생성
    pc = RTCPeerConnection()
    pc.addTrack(ScreenTrack())

    # 데이터 채널 열고, 제어 명령 수신 핸들러 등록
    dc = pc.createDataChannel("control")
    @dc.on("message")
    def on_control(msg):
        cmd = json.loads(msg)
        if cmd["type"] == "mouse":
            x, y = cmd["x"], cmd["y"]
            pyautogui.moveTo(x, y)
            if cmd.get("click"):
                pyautogui.click()
        elif cmd["type"] == "key":
            pyautogui.press(cmd["key"])

    # ICE candidate 발생 시 시그널링 서버로 전송
    @pc.on("ice-candidate")
    async def on_ice(event):
        if event.candidate:
            c = event.candidate
            # candidate string, sdpMid, sdpMLineIndex 순서로 튜플 전송
            await sio.emit("ice-candidate", (c.candidate, c.sdpMid, c.sdpMLineIndex))

    # 시그널링 이벤트들 정의
    @sio.event
    async def connect():
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
        print("📝 Get sdp ")
        if (data["type"] == "answer"):
            answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
            await pc.setRemoteDescription(answer)


    
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


    @sio.event
    async def disconnect():
        print("❌ Signaling 서버 연결 해제")

    # 서버 접속
    await sio.connect("http://localhost:3000")
    await sio.wait()

if __name__ == "__main__":
    asyncio.run(run())
