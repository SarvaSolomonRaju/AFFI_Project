# Deploy AFFI for free public review

Goal: a link anyone can open in a browser to review the dashboard — works when
your laptop is off, handles 50+ people, and costs **$0**.

This runs the full live stack (map, forecasts, charts, the assistant, the
6-hourly auto-refresh) on a **free-forever cloud VM**. The recommended host is
**Oracle Cloud "Always Free"**, which gives a VM that never expires and never
charges. Any Ubuntu VM with ~4 GB RAM works the same way.

You do this once; after that it stays up on its own.

---

## Overview (what you'll do)

1. Make a free Oracle Cloud account and create an "Always Free" VM.
2. Open port **80** to the internet.
3. Install Docker on the VM.
4. Upload the project as one file and start it.
5. Share `http://<your-server-ip>/`.

Total time: ~30–45 minutes, mostly waiting for the first build.

---

## 1. Create the free VM (Oracle Cloud Always Free)

1. Sign up at <https://www.oracle.com/cloud/free/>. It asks for a credit card
   to verify identity but the **Always Free** resources never charge. Pick a
   home region close to your reviewers.
2. In the console: **Compute → Instances → Create Instance**.
   - **Image:** Canonical Ubuntu 22.04.
   - **Shape:** click *Change shape* → **Ampere (Arm)** → `VM.Standard.A1.Flex`
     → set **2 OCPUs** and **12 GB RAM** (well within Always Free; you can go
     up to 4 OCPU / 24 GB free).
   - **SSH keys:** let it generate a key pair and **download the private key**
     (you'll need it to log in).
   - Create. Note the instance's **public IP address**.

> If Arm capacity is unavailable in your region, the free AMD shape
> (`VM.Standard.E2.1.Micro`, 1 GB RAM) is too small for this stack — try a
> different region, or use any other cloud's small Ubuntu VM (~4 GB RAM).

## 2. Open port 80

Two layers block ports on Oracle by default — do **both**:

**a) Security list (cloud firewall):** In the console, open your VM's **VCN →
Security Lists → Default Security List → Add Ingress Rule**:
- Source CIDR `0.0.0.0/0`, IP Protocol `TCP`, Destination Port `80`.

**b) The VM's own firewall** (Oracle Ubuntu images ship with iptables rules
that block everything). SSH in (next step) and run:
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save    # keep it across reboots
```

## 3. Log in and install Docker

From your laptop (use the private key you downloaded):
```bash
ssh -i /path/to/your-key.key ubuntu@<YOUR-SERVER-IP>
```
On the VM:
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu     # run docker without sudo
# log out and back in once so the group takes effect:
exit
```
SSH back in, then enable amd64 emulation (the GIS libraries ship as amd64;
this one command lets the Arm VM build and run them):
```bash
docker run --privileged --rm tonistiigi/binfmt --install amd64
```
(Skip this command only if your VM is already an x86_64/amd64 machine.)

## 4. Upload the project and start it

The trained models and flood data aren't in Git (they're large), so ship the
whole working folder as one file.

**On your laptop**, in the project folder:
```bash
bash scripts/bundle_for_deploy.sh          # creates affi-deploy.tgz (~300 MB)
scp -i /path/to/your-key.key affi-deploy.tgz ubuntu@<YOUR-SERVER-IP>:~/
```

**On the VM:**
```bash
mkdir -p affi && tar xzf affi-deploy.tgz -C affi && cd affi
docker compose -f docker-compose.prod.yml up -d --build
```
The first build takes ~15–25 minutes on the Arm VM (it builds the map/GIS
libraries under emulation). Watch progress with
`docker compose -f docker-compose.prod.yml logs -f`. When the `api` container
is healthy, you're live.

## 5. Share the link

Open **`http://<YOUR-SERVER-IP>/`** in any browser and share that URL. It stays
up on its own (`restart: unless-stopped`), survives reboots, and easily handles
50+ people reviewing at once (the site is served by nginx; the API is read-only
with 2 workers).

Check it's healthy any time:
```bash
docker compose -f docker-compose.prod.yml ps
curl -s http://localhost/health
```

---

## Optional: a real domain + HTTPS (padlock)

Reviewers will see a "not secure" note on plain `http://`. To get a nice URL
with HTTPS for free:
1. Point a domain (or a free one) at the server's IP (an `A` record).
2. Put [Caddy](https://caddyserver.com) in front — it fetches a free Let's
   Encrypt certificate automatically. Minimal `Caddyfile`:
   ```
   your-domain.com {
       reverse_proxy localhost:80
   }
   ```
   Run Caddy (or add it as a container) and open port 443 the same way you
   opened 80. That's the only change needed.

## Updating later

Re-bundle on your laptop, re-upload, and rebuild on the VM:
```bash
# laptop
bash scripts/bundle_for_deploy.sh
scp -i key.key affi-deploy.tgz ubuntu@<IP>:~/
# VM
tar xzf ~/affi-deploy.tgz -C ~/affi && cd ~/affi
docker compose -f docker-compose.prod.yml up -d --build
```

## Cost

$0. Oracle Always Free never expires and never charges for the Arm VM within
its free limits. There is no per-visitor cost — the assistant runs locally on
the server, and all data sources are free/public.

## Troubleshooting

- **Page won't load:** you almost certainly missed the VM's local iptables rule
  (step 2b) or the security-list rule (2a). Both are required.
- **First build fails on a GIS library (rasterio/GDAL) with an "exec format"
  or wheel error:** you skipped the amd64-emulation command in step 3
  (`docker run --privileged --rm tonistiigi/binfmt --install amd64`). Run it,
  then rebuild. If it instead ran out of memory, use the 2 OCPU / 12 GB Arm
  shape, not the 1 GB micro.
- **Images/maps blank:** confirm the `api` container is healthy
  (`docker compose -f docker-compose.prod.yml ps`); nginx proxies `/api` and
  `/outputs` to it.
