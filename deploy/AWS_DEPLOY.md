# Deploying the hosted demo on AWS EC2

One small server runs the app in Docker, with Caddy in front for automatic HTTPS (needed for the
microphone and voice-note features). AI calls go to Bedrock / Groq / Gemini using keys that live
only in a locked file on the server.

## 1. Console (region: Asia Pacific (Mumbai) ap-south-1)

1. **EC2 → Key pairs → Create key pair**: name `nirikshak-key`, type ED25519, format `.pem`.
   It downloads to `~/Downloads/nirikshak-key.pem`.
2. **EC2 → Instances → Launch instance**:
   - Name `nirikshak-demo`; image **Amazon Linux 2023** (x86_64)
   - Instance type **m7i-flex.large** (2 vCPU, 8 GB; free-tier eligible)
   - Key pair `nirikshak-key`
   - Network settings: create a security group with **Allow SSH from My IP**, **Allow HTTPS from
     the internet** and **Allow HTTP from the internet**
   - Storage **30 GiB gp3**
3. When it is **Running**, copy the **Public IPv4 address** (called `IP` below).

## 2. Laptop

```bash
chmod 400 ~/Downloads/nirikshak-key.pem
# app bundle (code + demo data, no secrets)
scp -i ~/Downloads/nirikshak-key.pem ~/nirikshak-deploy.tar.gz ec2-user@IP:~
# API keys for the server only (the Hugging Face token is not needed there)
grep -v '^HF_TOKEN' ~/.config/nirikshak/env > /tmp/app.env
scp -i ~/Downloads/nirikshak-key.pem /tmp/app.env ec2-user@IP:~ && rm /tmp/app.env
ssh -i ~/Downloads/nirikshak-key.pem ec2-user@IP
```

## 3. Server

```bash
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
exit            # log out and ssh in again so the docker group applies
```

```bash
chmod 600 ~/app.env
tar -xzf nirikshak-deploy.tar.gz && cd nirikshak
docker build -t nirikshak .                 # 5-10 minutes

docker network create web
docker run -d --name app --restart unless-stopped --network web --env-file ~/app.env nirikshak

DOMAIN=$(curl -s https://checkip.amazonaws.com | tr . -).sslip.io
docker run -d --name caddy --restart unless-stopped --network web -p 80:80 -p 443:443 \
  -v caddy_data:/data caddy:2 caddy reverse-proxy --from "$DOMAIN" --to app:7860
echo "https://$DOMAIN"
```

Open the printed `https://…sslip.io` address (the certificate takes ~30 s on first visit).

## Checks and maintenance

```bash
docker logs -f app        # app log; the header badge should read "Public demo" with the cloud model
docker logs caddy         # HTTPS certificate status
docker restart app        # after editing ~/app.env
```

- The public IP (and so the URL) changes if the instance is **stopped**; attach an Elastic IP to
  keep it fixed.
- To shut everything down: terminate the instance, then delete its security group and key pair.
