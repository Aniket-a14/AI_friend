# Deployment Guide 🚀🚢

AI Friend can be deployed in two main ways: **Split** (Recommended for ease) or **Combined** (Best for control).

---

## 🛡️ Production Checklist (Do this First)

1. **SSL/HTTPS**: **NON-NEGOTIABLE**. Modern browsers will block the microphone on any site without a valid SSL certificate.
2. **Environment Safety**: Ensure `.env` files are in your `.gitignore`.
3. **Database**: Use a production-grade Supabase connection string.

---

## ☁️ Strategy 1: Split Deployment (Highly Recommended)
*Best for: Speed, auto-scaling, and easy management.*

### 1. Frontend -> [Vercel](https://vercel.com)
Vercel is built for Next.js.
- **Connect**: Link your GitHub repo.
- **Configure**: Set "Root Directory" to `frontend`.
- **Environment**: Add `NEXT_PUBLIC_WS_URL` pointing to your Railway backend.

### 2. Backend -> [Railway.app](https://railway.app)
Vercel's serverless functions can't handle long-running WebSockets.
- **How**: Point Railway to your `backend` folder. It will use the `Dockerfile` automatically.
- **Benefit**: Supports persistent WebSocket connections for real-time audio.

---

## 🐳 Strategy 2: Combined Monolith (Total Control)
*Best for: Hardcore developers, minimizing costs, or hosting on your own server (DigitalOcean, AWS EC2, Linode).*

This uses the included `docker-compose.yml` to run everything together.

### 1. Setup your Server (VPS)
- Install **Docker** and **Docker Compose**.
- Point your domain's A-record to the server IP.

### 2. Deploy the Stack
```bash
git clone <your-repo-url>
cd Ai_friend
# Build and run everything in the background
docker-compose up --build -d
```

### 3. Setup SSL (Reverse Proxy)
Use **Nginx Proxy Manager** or **Caddy** to:
- Map `your-domain.com` -> `localhost:3000` (Frontend).
- Map `your-domain.com/ws` -> `localhost:8000` (Backend WebSocket).
- Automatically generate **Let's Encrypt** SSL certificates.

---

## �️ Testing Microphones without SSL
If you are testing on a server before setting up HTTPS, you must tell Chrome to trust your IP:
1. Open Chrome and go to `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.
2. Add your server's IP (e.g., `http://123.45.67.89:3000`).
3. Enable and Restart.

---

## 🌍 Where is my code actually?
In both cases, **GitHub** is your bridge. You push your code there, and your server (Vercel/Railway or your VPS) pulls it to build the final app.
