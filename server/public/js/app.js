const socket = io();

const myFace = document.getElementById("myFace");
const muteBtn = document.getElementById("mute");
const cameraBtn = document.getElementById("camera");
const camerasSelect = document.getElementById("cameras");
const call = document.getElementById("call");
const sendBtn = document.getElementById("sendBtn");

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

socket.on("offer", async (offer) => {
  // OK
  console.log("received the offer");
  console.log("offer: ", offer);
  myPeerConnection.setRemoteDescription(offer);
  const answer = await myPeerConnection.createAnswer();
  myPeerConnection.setLocalDescription(answer);
  console.log("answer: ", answer);
  socket.emit("answer", answer);
  console.log("sent the answer");
});

socket.on("answer", (answer) => {
  console.log("answer: ", answer);
  console.log("received the answer");
  myPeerConnection.setRemoteDescription(answer);
});

socket.on("ice", (ice) => {
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
  if(data== null || data.candidate == null) return
      socket.emit("ice", {
     candidate: data.candidate.candidate,
      sdpMid: data.candidate.sdpMid,
      sdpMLineIndex: data.candidate.sdpMLineIndex
    }); 
}

let remoteStream = null;
// function handleAddStream(event) {      // ← event 라는 이름으로 선언
//   const peerFace = document.getElementById("peerFace");
//   remoteStream = event.stream;        // event.stream 으로 접근
//   peerFace.srcObject = remoteStream;

//   peerFace.addEventListener("click", (clickEvent) => {
//     if (!controlChannel || controlChannel.readyState !== "open") return;

//     const rect = peerFace.getBoundingClientRect();
//     const videoW = peerFace.videoWidth;
//     const videoH = peerFace.videoHeight;

//     const x = Math.round((clickEvent.clientX - rect.left) * (videoW / rect.width));
//     const y = Math.round((clickEvent.clientY - rect.top)  * (videoH / rect.height));

//     controlChannel.send(JSON.stringify({ type: "mouse", x, y, click: true }));
//   });
// }
// function handleAddStream(event) {
//   const peerFace = document.getElementById("peerFace");
//   const remoteStream = event.stream;
//   peerFace.srcObject = remoteStream;

//   // 축소 비율
//   const scale = 3 / 5;

//   // 메타데이터가 로드된 뒤에 해상도를 읽어서 요소 크기를 맞춰줍니다.
//   peerFace.onloadedmetadata = () => {
//     const videoW = peerFace.videoWidth;
//     const videoH = peerFace.videoHeight;
//     console.log("원본 해상도:", videoW, "x", videoH);

//     // 표시 크기 = 원본 * scale
//     const dispW = Math.round(videoW * scale);
//     const dispH = Math.round(videoH * scale);

//     peerFace.width = dispW;
//     peerFace.height = dispH;
//     peerFace.style.width  = dispW + "px";
//     peerFace.style.height = dispH + "px";
//   };

//   // 클릭 핸들러: 클릭 위치를 원본 좌표로 역변환
//   peerFace.addEventListener("click", (e) => {
//     if (!controlChannel || controlChannel.readyState !== "open") return;

//     // e.offsetX/Y 는 표시 크기 기준이므로, 원본 좌표로 환산
//     const rawX = Math.round(e.offsetX / scale);
//     const rawY = Math.round(e.offsetY / scale);

//     controlChannel.send(JSON.stringify({
//       type: "mouse",
//       x: rawX,
//       y: rawY,
//       click: true
//     }));
//   });

//   // 키 입력은 그대로 원본 스트림에 전달
//   window.addEventListener("keydown", (e) => {
//     if (!controlChannel || controlChannel.readyState !== "open") return;
//     controlChannel.send(JSON.stringify({ type: "key", key: e.key }));
//   });
// }

function handleAddStream(event) {
  const peerFace = document.getElementById("peerFace");
  const remoteStream = event.stream;
  peerFace.srcObject = remoteStream;

  const scale = 3 / 5;
  peerFace.onloadedmetadata = () => {
    const videoW = peerFace.videoWidth;
    const videoH = peerFace.videoHeight;
    const dispW = Math.round(videoW * scale);
    const dispH = Math.round(videoH * scale);
    peerFace.width = dispW;
    peerFace.height = dispH;
    peerFace.style.width  = dispW + "px";
    peerFace.style.height = dispH + "px";
  };

  // 클릭 핸들러
  peerFace.addEventListener("click", (e) => {
    if (!controlChannel || controlChannel.readyState !== "open") return;
    const rawX = Math.round(e.offsetX / scale);
    const rawY = Math.round(e.offsetY / scale);
    controlChannel.send(JSON.stringify({
      type: "mouse", x: rawX, y: rawY, click: true
    }));
  });

  // 드래그 핸들러
  let isDragging = false;
  let startX = 0, startY = 0;

  peerFace.addEventListener("mousedown", (e) => {
    isDragging = true;
    startX = e.offsetX;
    startY = e.offsetY;
  });
  peerFace.addEventListener("mousemove", (e) => {
    if (!isDragging || !controlChannel || controlChannel.readyState !== "open") return;
    const currentX = e.offsetX;
    const currentY = e.offsetY;

    const rawStartX   = Math.round(startX   / scale);
    const rawStartY   = Math.round(startY   / scale);
    const rawCurrentX = Math.round(currentX / scale);
    const rawCurrentY = Math.round(currentY / scale);

    controlChannel.send(JSON.stringify({
      type:    "drag",
      startX:  rawStartX,
      startY:  rawStartY,
      currentX: rawCurrentX,
      currentY: rawCurrentY
    }));
  });
  window.addEventListener("mouseup", () => {
    isDragging = false;
  });

  // 키 입력
  window.addEventListener("keydown", (e) => {
    if (!controlChannel || controlChannel.readyState !== "open") return;
    controlChannel.send(JSON.stringify({ type: "key", key: e.key }));
  });
}


sendBtn.addEventListener("click", async (event) => {
  event.preventDefault();

  const payload = {
    title: "画面共有",
    body: "画面共有の要請があります",
    payload: "CC212C",
  };

  try {
    // 2) fetch로 POST 요청 보내기
    const response = await fetch("http://192.168.3.72:3000/api/send-push", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    // 3) 응답 처리
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const result = await response.json();
    console.log("서버 응답:", result);
  } catch (err) {
    console.error("전송 중 에러:", err);
  }
});

// 전역에 controlChannel 변수 선언
let controlChannel = null;