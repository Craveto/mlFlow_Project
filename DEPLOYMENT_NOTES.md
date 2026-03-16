# Deployment Notes

## Azure VM Hosting Reference

Use this document as the short step-by-step reference for hosting the real BTCUSD forecasting project on an Azure Virtual Machine.

Final architecture:

`Browser -> Azure Public IP -> Nginx -> localhost:8000 -> run_project.py -> Django app`

---

## 1. Identify the Real Project Folder

Use the folder that contains `run_project.py`, not the placeholder scaffold.

Example:

`E:\Bizmetric\Trae\TimeSeriesModels\timesereisAmolSir\timeseries`

Short note:
Azure will only show the app from the folder you actually copy.

---

## 2. Copy the Real Project to the Azure VM

Run this from your Windows machine:

```powershell
scp -r "E:\Bizmetric\Trae\TimeSeriesModels\timesereisAmolSir\timeseries" azureuser@20.205.20.100:~/
```

Short note:
Run `scp` on Windows, not inside the VM.

---

## 3. SSH Into the VM

```powershell
ssh azureuser@20.205.20.100
```

Short note:
All server setup commands run inside the VM after this.

---

## 4. Install Required Server Packages

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx git
```

Short note:
This prepares Ubuntu for Python app hosting.

---

## 5. Create a Python Virtual Environment

```bash
python3 -m venv /home/azureuser/timeseries/venv
source /home/azureuser/timeseries/venv/bin/activate
pip install --upgrade pip
pip install -r /home/azureuser/timeseries/requirements.txt
```

Short note:
Always install project dependencies inside the venv.

---

## 6. Verify the Real Project Files Exist on VM

```bash
ls -la /home/azureuser/timeseries
```

Short note:
Confirm `run_project.py`, `dashboard`, `src`, `data`, `artifacts`, and related files are present.

---

## 7. Update Django ALLOWED_HOSTS

Edit the actual settings file:

```bash
nano /home/azureuser/timeseries/dashboard/dashboard/settings.py
```

Set:

```python
ALLOWED_HOSTS = ["20.205.20.100", "127.0.0.1", "localhost"]
```

Short note:
Without this, Django throws `DisallowedHost`.

---

## 8. Test the App Manually First

```bash
cd /home/azureuser/timeseries
source /home/azureuser/timeseries/venv/bin/activate
python run_project.py --host 0.0.0.0 --port 8000 --skip-train
```

Open:

`http://20.205.20.100:8000`

Short note:
Manual test first. Service later.

---

## 9. Open Azure Inbound Ports

In Azure Portal, allow:

- `22` for SSH
- `80` for HTTP
- `8000` temporarily for testing

Short note:
If the browser times out, this is usually the reason.

---

## 10. Create systemd Service

Create:

```bash
sudo nano /etc/systemd/system/timeseries.service
```

Use:

```ini
[Unit]
Description=BTCUSD TimeSeries app
After=network.target

[Service]
User=azureuser
Group=www-data
WorkingDirectory=/home/azureuser/timeseries
Environment="PATH=/home/azureuser/timeseries/venv/bin"
ExecStart=/home/azureuser/timeseries/venv/bin/python /home/azureuser/timeseries/run_project.py --host 127.0.0.1 --port 8000 --skip-train
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Short note:
This makes the app run in the background automatically.

---

## 11. Start and Enable the Service

```bash
sudo systemctl daemon-reload
sudo systemctl restart timeseries
sudo systemctl enable timeseries
sudo systemctl status timeseries
```

Short note:
`active (running)` is the success condition.

---

## 12. Configure Nginx

Create:

```bash
sudo nano /etc/nginx/sites-available/timeseries
```

Use:

```nginx
server {
    listen 80;
    server_name 20.205.20.100;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        root /home/azureuser/timeseries/dashboard;
    }

    location / {
        include proxy_params;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Short note:
Nginx exposes the app on the public IP.

---

## 13. Disable Default Nginx Site and Enable Your App

```bash
sudo rm /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/timeseries /etc/nginx/sites-enabled/timeseries
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

Short note:
If the default site stays enabled, you see the Nginx welcome page.

---

## 14. Open the Final Hosted URL

Use:

`http://20.205.20.100`

Short note:
This is the final public app URL for the demo.

---

## 15. Quick Health Checks

```bash
sudo systemctl status timeseries
sudo systemctl status nginx
```

Short note:
Use these before any demo.

---

## Common Problems

### Windows Path Error in scp
Cause:
Running `scp` inside the Linux VM.

Fix:
Run `scp` from Windows PowerShell.

### ERR_CONNECTION_TIMED_OUT
Cause:
Port `8000` not open in Azure for testing.

Fix:
Open `8000` temporarily in Azure inbound rules.

### Nginx Welcome Page
Cause:
Default Nginx site still enabled.

Fix:
Remove `/etc/nginx/sites-enabled/default`.

### 502 Bad Gateway
Cause:
Nginx cannot reach the app service.

Fix:
Check `timeseries.service` and proxy target `127.0.0.1:8000`.

### DisallowedHost
Cause:
Azure public IP missing from Django `ALLOWED_HOSTS`.

Fix:
Add:

```python
ALLOWED_HOSTS = ["20.205.20.100", "127.0.0.1", "localhost"]
```

---

## Final Reminder

The project that should be hosted is the real one containing `run_project.py`, not the placeholder Django scaffold.
