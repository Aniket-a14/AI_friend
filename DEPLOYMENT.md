# Deployment Guide 🚀🚢

This guide provides a roadmap for deploying Pankudi AI to a production environment (VPS, AWS, etc.).

## 🛡️ Production Checklist

1. **Environment Variables**: Ensure all API keys in `.env` are secure and not committed to Git.
2. **Database**: Use a production-grade Supabase project (transaction pooling recommended).
3. **SSL/HTTPS**: **CRITICAL**. Modern browsers strictly require HTTPS to allow microphone access.

## 🐳 Option 1: Docker (Recommended)

The easiest way to go live. Ensure Docker and Docker Compose are installed on your server.

1. **Clone & Config**:
   ```bash
   git clone <your-repo>
   cd Pankudi_ai
   # Build the production images
   docker-compose up --build -d
   ```

2. **Reverse Proxy**: Use Nginx or Traefik to handle SSL termination and proxy requests to `localhost:3000` (Frontend) and `localhost:8000` (Backend).

## 🔒 Security Hardening

- **CORS**: Set `ALLOWED_ORIGINS` in your backend `.env` to your production domain (e.g., `https://pankudi.yoursite.com`).
- **Secrets**: Use a secret manager or encrypted environment variables in your CI/CD pipeline.

## 🎙️ Microphone Access (Important)

If you deploy to a server without HTTPS:
- **Chrome**: You can bypass this for testing by going to `chrome://flags/#unsafely-treat-insecure-origin-as-secure` and adding your IP.
- **Production**: You **MUST** use a valid SSL certificate (Let's Encrypt is perfect).

## 🌍 Infrastructure Recommendations

- **Server**: At least 2GB RAM (Whisper/Gemini processing can be memory-intensive).
- **Network**: Low-latency connection to OpenAI/ElevenLabs/Google endpoints.
