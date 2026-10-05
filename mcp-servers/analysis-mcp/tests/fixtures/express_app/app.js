const express = require("express");
const db = require("./db");

const app = express();

function reachDatabase() {
  return db.query("notes");
}

app.get("/notes", function (req, res) {
  res.send(reachDatabase());
});

module.exports = app;
