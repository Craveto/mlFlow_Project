# Split Hosting on Azure VM

This setup runs:

- `frontend` on `127.0.0.1:3000`
- `backend` on `127.0.0.1:8000`
- `nginx` on port `80`

Public flow:

`Browser -> Nginx -> frontend (/)`
`Browser -> Nginx -> backend (/api/)`

## Recommended Option

Use `systemd` for both services.

Files included:

- `deploy/systemd/timeseries-backend.service`
- `deploy/systemd/timeseries-frontend.service`
- `deploy/nginx/timeseries-split.conf`

Optional:

- `deploy/pm2/ecosystem.config.js`

## 1. Copy updated project to VM

Run from Windows:

```powershell
scp -r "E:\Bizmetric\Trae\TimeSeriesModels\timesereisAmolSir\timeseries" azureuser@20.205.20.100:~/
```

## 2. SSH into VM

```powershell
ssh azureuser@20.205.20.100
```

## 3. Install dependencies if needed

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx git
```

## 4. Backend setup

```bash
python3 -m venv /home/azureuser/timeseries/venv
source /home/azureuser/timeseries/venv/bin/activate
pip install --upgrade pip
pip install -r /home/azureuser/timeseries/requirements.txt
```

## 5. Test backend manually

```bash
cd /home/azureuser/timeseries
source /home/azureuser/timeseries/venv/bin/activate
python run_project.py --host 127.0.0.1 --port 8000 --skip-train
```

In another terminal on the VM:

```bash
curl http://127.0.0.1:8000/api/overview/
```

Stop with `Ctrl+C`.

## 6. Test frontend manually

```bash
cd /home/azureuser/timeseries/frontend
python3 -m http.server 3000 --bind 127.0.0.1
```

In another terminal on the VM:

```bash
curl http://127.0.0.1:3000
```

Stop with `Ctrl+C`.

## 7. Install systemd service files

```bash
sudo cp /home/azureuser/timeseries/deploy/systemd/timeseries-backend.service /etc/systemd/system/
sudo cp /home/azureuser/timeseries/deploy/systemd/timeseries-frontend.service /etc/systemd/system/
```

## 8. Start services

```bash
sudo systemctl daemon-reload
sudo systemctl enable timeseries-backend
sudo systemctl enable timeseries-frontend
sudo systemctl restart timeseries-backend
sudo systemctl restart timeseries-frontend
sudo systemctl status timeseries-backend
sudo systemctl status timeseries-frontend
```

## 9. Install Nginx config

```bash
sudo cp /home/azureuser/timeseries/deploy/nginx/timeseries-split.conf /etc/nginx/sites-available/timeseries
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/timeseries /etc/nginx/sites-enabled/timeseries
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

## 10. Open in browser

```text
http://20.205.20.100
```

## 11. Health checks

```bash
sudo systemctl status timeseries-backend
sudo systemctl status timeseries-frontend
sudo systemctl status nginx
curl http://127.0.0.1:8000/api/overview/
curl http://127.0.0.1:3000
```

## PM2 Option

Install:

```bash
sudo apt install -y nodejs npm
sudo npm install -g pm2
```

Run:

```bash
cd /home/azureuser/timeseries
pm2 start deploy/pm2/ecosystem.config.js
pm2 save
pm2 startup
```

Use PM2 only if you specifically want one process manager for both apps. For this project, `systemd` remains the better default.
