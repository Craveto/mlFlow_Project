module.exports = {
  apps: [
    {
      name: "timeseries-backend",
      script: "/home/azureuser/timeseries/venv/bin/python",
      args: "/home/azureuser/timeseries/run_project.py --host 127.0.0.1 --port 8000 --skip-train --no-reload",
      cwd: "/home/azureuser/timeseries",
      interpreter: "none",
      autorestart: true,
      watch: false,
    },
    {
      name: "timeseries-frontend",
      script: "/usr/bin/python3",
      args: "-m http.server 3000 --bind 127.0.0.1",
      cwd: "/home/azureuser/timeseries/frontend",
      interpreter: "none",
      autorestart: true,
      watch: false,
    },
  ],
};
