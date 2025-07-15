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
// app.get("/*", (req, res) => res.redirect("/"));


const handleListen = () => console.log(`Listening on http://localhost:3000`);
// app.listen(3000, handleListen);
const httpServer = http.createServer(app);
const wsServer = new Server(httpServer, {});

wsServer.on("connection", (socket) => {
  console.log("connection");

  socket.on("join_room", (roomName) => {
    console.log("JOIN ");
    console.log("roomName: ", roomName);
    socket.join(roomName);
  });

  socket.on("offer", (data) => {
    console.log("Get offer");
    
    socket.to("1212").emit("offer", data);
  });
  socket.on("answer", (data, roomName) => {
    console.log("Get answer");
    socket.to("1212").emit("answer", data);
  });
  socket.on("ice", (data) => {
    console.log("Get ice");
    socket.to("1212").emit("ice", data);
  });
});
httpServer.listen(3000, handleListen);
