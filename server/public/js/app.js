const socket = io();

const myFace = document.getElementById("myFace");
const muteBtn = document.getElementById("mute");
const cameraBtn = document.getElementById("camera");
const camerasSelect = document.getElementById("cameras");
const call = document.getElementById("call");

call.hidden = true;

let muted = false;
let cameraOff = false;
let roomName;
let myPeerConnection;

const welcome = document.getElementById("welcome");
const welcomeForm = welcome.querySelector("form");

async function initCall() {
  welcome.hidden = true;
  call.hidden = false;
  // await getMedia();
  makeConnection();
}

async function handleWelcomeSubmit(event) {
  event.preventDefault();
  const input = welcomeForm.querySelector("input");
  await initCall();
  socket.emit("join_room", input.value);
  roomName = input.value;
  input.value = "";
}

welcomeForm.addEventListener("submit", handleWelcomeSubmit);

// Socket Code

socket.on("welcome", async () => {
  // OK
  const offer = await myPeerConnection.createOffer();
  myPeerConnection.setLocalDescription(offer);
  console.log("sent the offer");
  socket.emit("offer", offer);
});

socket.on("sdp", async (data) => {
  console.log("▶️ got SDP", data.type);
  if (data.type === "offer") {
    // iOS가 보낸 offer 처리
    await myPeerConnection.setRemoteDescription(data);
    const answer = await myPeerConnection.createAnswer();
    await myPeerConnection.setLocalDescription(answer);
    console.log("▶️ send answer", answer);
    socket.emit("sdp", {
      type: answer.type,
      sdp: answer.sdp,
    });
  }
});

socket.on("ice-candidate", (ice) => {
  if (ice) {
    console.log("received candidate", ice);
    myPeerConnection.addIceCandidate(ice);
  }
});

// RTC Code

function makeConnection() {
  myPeerConnection = new RTCPeerConnection();
  myPeerConnection.addEventListener("icecandidate", handleIce);
  myPeerConnection.addEventListener("addstream", handleAddStream);
  // myStream.getTracks().forEach((track) => myPeerConnection.addTrack(track, myStream));

  myPeerConnection.ondatachannel = (event) => {
    controlChannel = event.channel;
    controlChannel.onopen = () => console.log("🟢 control channel open");
    controlChannel.onmessage = (e) => console.log("← control msg:", e.data);
  };
}

function handleIce(data) {
  console.log("data: ", data);
  console.log("sent candidate");
  // socket.emit("ice", data.candidate);
  if (data == null || data.candidate == null) return;
  socket.emit("ice-candidate", {
    candidate: data.candidate.candidate,
    sdpMid: data.candidate.sdpMid,
    sdpMLineIndex: data.candidate.sdpMLineIndex,
  });
}

let remoteStream = null;

function handleAddStream(event) {
  const peerFace = document.getElementById("peerFace");
  const remoteStream = event.stream;
  peerFace.srcObject = remoteStream;

  // 축소 비율
  const scale = 3 / 5;

  // 메타데이터가 로드된 뒤에 해상도를 읽어서 요소 크기를 맞춰줍니다.
  peerFace.onloadedmetadata = () => {
    const videoW = peerFace.videoWidth;
    const videoH = peerFace.videoHeight;
    console.log("원본 해상도:", videoW, "x", videoH);

    // 표시 크기 = 원본 * scale
    const dispW = Math.round(videoW * scale);
    const dispH = Math.round(videoH * scale);

    peerFace.width = dispW;
    peerFace.height = dispH;
    peerFace.style.width = dispW + "px";
    peerFace.style.height = dispH + "px";
  };

  // 클릭 핸들러: 클릭 위치를 원본 좌표로 역변환
  peerFace.addEventListener("click", (e) => {
    if (!controlChannel || controlChannel.readyState !== "open") return;

    // e.offsetX/Y 는 표시 크기 기준이므로, 원본 좌표로 환산
    const rawX = Math.round(e.offsetX / scale);
    const rawY = Math.round(e.offsetY / scale);

    controlChannel.send(
      JSON.stringify({
        type: "mouse",
        x: rawX,
        y: rawY,
        click: true,
      })
    );
  });

  // 키 입력은 그대로 원본 스트림에 전달
  window.addEventListener("keydown", (e) => {
    if (!controlChannel || controlChannel.readyState !== "open") return;

    if (e.repeat) return;
    controlChannel.send(JSON.stringify({ type: "key", key: e.key }));
  });
  peerFace.addEventListener("wheel", (e) => {
      if (!controlChannel || controlChannel.readyState !== "open") return;
      // 브라우저 기본 스크롤 방지
      e.preventDefault();
      // deltaY > 0 이면 아래로, < 0 이면 위로 스크롤
      const delta = Math.sign(e.deltaY) * 120;
      controlChannel.send(
        JSON.stringify({
          type: "wheel",
          delta,
        })
      );
    }, { passive: false });
  let isDragging = false;

  peerFace.addEventListener("mousedown", e => {
    isDragging = true;
    const rawX = Math.round(e.offsetX / scale);
    const rawY = Math.round(e.offsetY / scale);
    controlChannel.send(JSON.stringify({
      type: "drag_start",
      x: rawX,
      y: rawY
    }));
  });

  peerFace.addEventListener("mousemove", e => {
    if (!isDragging) return;
    const rawX = Math.round(e.offsetX / scale);
    const rawY = Math.round(e.offsetY / scale);
    controlChannel.send(JSON.stringify({
      type: "drag_move",
      x: rawX,
      y: rawY
    }));
  });

  window.addEventListener("mouseup", e => {
    if (!isDragging) return;
    isDragging = false;
    // 화면 바깥에서 mouseUp 이 발생해도 drag_end 처리
    const rawX = Math.round(e.clientX / scale);
    const rawY = Math.round(e.clientY / scale);
    controlChannel.send(JSON.stringify({
      type: "drag_end",
      x: rawX,
      y: rawY
    }));
  });
}

// 전역에 controlChannel 변수 선언
let controlChannel = null;
