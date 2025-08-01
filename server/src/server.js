import bodyParser from "body-parser";
import http from "http";
import { Server } from "socket.io";
import express from "express";
import path from "path";

const __dirname = path.resolve();
const app = express();
app.use(bodyParser.json());
app.set("view engine", "pug");
app.set("views", __dirname + "/views");
app.use("/public", express.static(__dirname + "/public"));
app.get("/", (_, res) => res.render("home"));

const httpServer = http.createServer(app);
const io = new Server(httpServer, {
  cors: { origin: "*" },
});

// 접속 허용 최대 수
const MAX_CLIENTS = 2;
const clients = []; // 순서 보장 위해 Array 사용

io.on("connection", (socket) => {
  // 허용치 초과 시: 가장 오래된 소켓 끊기
  if (clients.length >= MAX_CLIENTS) {
    const oldestId = clients.shift(); // 배열 맨 앞 ID
    const oldestSocket = io.sockets.sockets.get(oldestId);
    if (oldestSocket) {
      console.log("🔴 disconnecting oldest client:", oldestId);
      oldestSocket.emit("error", "새 클라이언트가 연결되어 강제 종료됩니다.");
      oldestSocket.disconnect(true);
    }
  }

  // 새 소켓 추가
  clients.push(socket.id);
  console.log(
    "🟢 connection:",
    socket.id,
    `(${clients.length}/${MAX_CLIENTS})`
  );

  // SDP/ICE 핸들러
  socket.on("sdp", (data) => {
    console.log("🔄 SDP from", socket.id, data.type);
    socket.broadcast.emit("sdp", data);
  });
  socket.on("ice-candidate", (data) => {
    console.log("❄️ ICE from", socket.id);
    socket.broadcast.emit("ice-candidate", data);
  });

  // 연결 해제 시 배열에서 제거
  socket.on("disconnect", () => {
    const idx = clients.indexOf(socket.id);
    if (idx !== -1) clients.splice(idx, 1);
    console.log(
      "⚪️ disconnect:",
      socket.id,
      `(${clients.length}/${MAX_CLIENTS})`
    );
  });
});

httpServer.listen(3000, () =>
  console.log("Listening on http://localhost:3000")
);
