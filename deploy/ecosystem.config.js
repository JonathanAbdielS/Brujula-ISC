// pm2 start deploy/ecosystem.config.js   (desde la raíz del proyecto)
module.exports = {
  apps: [{
    name: "brujula-isc",
    cwd: __dirname + "/..",
    script: "venv/bin/uvicorn",
    args: "app.main:app --host 127.0.0.1 --port 8010 --proxy-headers",
    interpreter: "none",
    autorestart: true,
    max_memory_restart: "300M",
  }],
};
