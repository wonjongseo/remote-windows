
import asyncio
import json

import mss
import numpy as np
import pyautogui
import socketio
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCIceCandidate,
    VideoStreamTrack,
)
from av import VideoFrame

# Signaling room name
ROOM = "1212"

class ScreenTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]

    async def recv(self):
        frame = self.sct.grab(self.monitor)
        arr = np.frombuffer(frame.rgb, dtype=np.uint8)
        arr = arr.reshape((frame.height, frame.width, 3))
        vf = VideoFrame.from_ndarray(arr, format="rgb24")
        vf.pts, vf.time_base = await self.next_timestamp()
        return vf

class WebRTCClient:
    def __init__(self, room=ROOM):
        self.sio = socketio.AsyncClient()
        self.pc = None
        self.room = room

        # signaling events
        self.sio.event(self.on_connect)
        self.sio.on("welcome", self.on_welcome)
        self.sio.on("answer", self.on_answer)
        self.sio.on("ice", self.on_remote_ice)

    async def run(self):
        # create peer connection and add track
        self.pc = RTCPeerConnection()
        self.pc.addTrack(ScreenTrack())

        # create data channel for control
        dc = self.pc.createDataChannel("control")
        @dc.on("message")
        def on_control(msg):
            cmd = json.loads(msg)
            if cmd.get("type") == "mouse":
                pyautogui.moveTo(cmd["x"], cmd["y"])
                if cmd.get("click"): pyautogui.click()
            elif cmd.get("type") == "key":
                pyautogui.press(cmd["key"])

        @self.pc.on("icecandidate")
        async def on_ice(evt):
            if evt.candidate:
                c = evt.candidate
                await self.sio.emit("ice", {
                    "candidate": c.candidate,
                    "sdpMid": c.sdpMid,
                    "sdpMLineIndex": c.sdpMLineIndex,
                })

        # connect signaling
        await self.sio.connect("http://localhost:3000", transports=["websocket"])
        await self.sio.emit("join_room", self.room)
        # wait for signaling events
        await self.sio.wait()

    async def on_connect(self):
        print("🔌 connected to signaling server")

    async def on_welcome(self):
        print("👋 welcome event received, sending offer")
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        await self.sio.emit("offer", {"sdp": offer.sdp, "type": offer.type})

    async def on_answer(self, data):
        print("✅ answer received")
        desc = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        await self.pc.setRemoteDescription(desc)

    async def on_remote_ice(self, data):
        if not data:
            return
        ice = RTCIceCandidate(
            data["candidate"], data["sdpMid"], data["sdpMLineIndex"]
        )
        await self.pc.addIceCandidate(ice)

    async def shutdown(self):
        if self.pc:
            await self.pc.close()
        await self.sio.disconnect()
