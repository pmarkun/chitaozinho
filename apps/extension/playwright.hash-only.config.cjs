const path = require("node:path");
module.exports = {
  testDir: path.join(__dirname, "e2e"),
  testMatch: "hash-capture.integration.cjs",
  workers: 1,
};
