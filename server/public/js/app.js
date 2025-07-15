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

// async function getCameras() {
//   try {
//     const devices = await navigator.mediaDevices.enumerateDevices();
//     const cameras = devices.filter((device) => device.kind === "videoinput");
//     const currentCamera = myStream.getVideoTracks()[0];
//     cameras.forEach((camera) => {
//       const option = document.createElement("option");
//       option.value = camera.deviceId;
//       option.innerText = camera.label;
//       if (currentCamera.label === camera.label) {
//         option.selected = true;
//       }
//       camerasSelect.appendChild(option);
//     });
//   } catch (e) {
//     console.log(e);
//   }
// }

// async function getMedia(deviceId) {
//   const initialConstrains = {
//     audio: true,
//     video: { facingMode: "user" },
//   };
//   const cameraConstraints = {
//     audio: true,
//     video: { deviceId: { exact: deviceId } },
//   };
//   try {
//     myStream = await navigator.mediaDevices.getUserMedia(deviceId ? cameraConstraints : initialConstrains);
//     myFace.srcObject = myStream;
//     if (!deviceId) {
//       await getCameras();
//     }
//   } catch (e) {
//     console.log(e);
//   }
// }

// function handleMuteClick() {
//   myStream.getAudioTracks().forEach((track) => (track.enabled = !track.enabled));
//   if (!muted) {
//     muteBtn.innerText = "Unmute";
//     muted = true;
//   } else {
//     muteBtn.innerText = "Mute";
//     muted = false;
//   }
// }
// function handleCameraClick() {
//   myStream.getVideoTracks().forEach((track) => (track.enabled = !track.enabled));
//   if (cameraOff) {
//     cameraBtn.innerText = "Turn Camera Off";
//     cameraOff = false;
//   } else {
//     cameraBtn.innerText = "Turn Camera On";
//     cameraOff = true;
//   }
// }

// async function handleCameraChange() {
//   //await getMedia(camerasSelect.value);
//   if (myPeerConnection) {
//     const videoTrack = myStream.getVideoTracks()[0];
//     const videoSender = myPeerConnection.getSenders().find((sender) => sender.track.kind === "video");
//     videoSender.replaceTrack(videoTrack);
//   }
// }

// muteBtn.addEventListener("click", handleMuteClick);
// cameraBtn.addEventListener("click", handleCameraClick);
// camerasSelect.addEventListener("input", handleCameraChange);

// Welcome Form (join a room)

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

function handleAddStream(data) {
  console.log("data: ", data);
  const peerFace = document.getElementById("peerFace");
  peerFace.srcObject = data.stream;
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