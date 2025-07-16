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

io.on("connection", (socket) => {
  console.log("🟢 connection:", socket.id);

  // SDP (offer/answer) 브로드캐스트
  socket.on("sdp", (data) => {
    console.log("🔄 SDP from", socket.id, data.type);
    socket.broadcast.emit("sdp", data);
  });

  // ICE 후보 브로드캐스트
  socket.on("ice-candidate", (data) => {
    console.log("❄️ ICE from", socket.id);
    console.log("❄️ ICE:", data);
    socket.broadcast.emit("ice-candidate", data);
  });
});

httpServer.listen(3000, () =>
  console.log("Listening on http://localhost:3000")
);
