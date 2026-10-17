# AI4ArtsEd DevServer - Operations Guide

> **Stand.** Geschrieben im November 2025, lag bis zum 2026-08-29 als `readme.md`
> im Wurzelverzeichnis — neben `README.md`, mit dem es sich auf jedem
> case-insensitiven Dateisystem (macOS, Windows) beim Klonen ins Gehege kam.
> Beim Umzug hierher sind die Pfade, die Zweig- und Dienstnamen auf den heutigen
> Stand gebracht; die Abschnitte „Troubleshooting" und „Common Operations" sind
> **nicht nachgeprüft** und können älter sein, als sie aussehen. Die belastbare
> Beschreibung des Deployments steht in `5_pullanddeploy.sh` selbst.

## Quick Reference

### Ports
- **5173** - Frontend Development Server (Vite)
- **17801** - Backend Development Server
- **17802** - Backend Production Server

### Start Scripts
Im Wurzelverzeichnis des Repos:
- `./3_start_backend_dev.sh` - Start backend development server
- `./4_start_frontend_dev.sh` - Start frontend development server

## Development Workflow

### Starting Development
1. Start backend dev server: `./3_start_backend_dev.sh`
2. Start frontend dev server: `./4_start_frontend_dev.sh`
3. Access frontend at `http://localhost:5173`
4. Backend API at `http://localhost:17801`

### Before Committing
1. Run type check: `cd public/ai4artsed-frontend && npm run type-check`
2. Build frontend: `npm run build`
3. Test that production build works
4. Commit changes

## Production Deployment

### Standard Deployment Procedure
1. **Build production frontend**:
   ```bash
   cd public/ai4artsed-frontend
   npm run build
   ```

2. **Commit and push** — entwickelt wird auf `develop`, nicht auf `main`.
   **Pfade einzeln nennen. Kein `git add -A`, kein `git add .`, kein
   `git commit -a`:** in diesem Arbeitsbaum liegen regelmäßig Dateien anderer
   Sitzungen und unversionierte Arbeitsdateien, und was einmal in einem
   Repository steht, steht dort dauerhaft.
   ```bash
   git add pfad/zur/datei.ts pfad/zur/anderen.vue
   git commit -m "your message"
   git push origin develop
   ```

3. **Auf der Produktionsmaschine** (eine andere Maschine als dieser DevServer)
   erledigt das ein Skript: `./5_pullanddeploy.sh` holt `main`, baut das
   Frontend und startet die Dienste neu.

### Production Backend
- Port: **17802**
- Serves both API and built frontend
- Check logs for errors after deployment

### Die systemd-Dienste
`ai4artsed-backend.service` (Flask, Port 17802), `ai4artsed-gpu.service`
(gpu_service), `ai4artsed-comfyui.service`. Neu starten — **ein Dienst je
Aufruf, mit vollem Pfad und `.service`**, sonst greift die NOPASSWD-Regel nicht
und es wird ein Passwort verlangt:

```bash
sudo -n /usr/bin/systemctl restart ai4artsed-backend.service
```

Eine Änderung nur am Frontend braucht keinen Neustart, nur `npm run build`.

## Common Operations

### Checking Running Services
```bash
# Check what's running on development ports
lsof -i :5173  # Frontend dev
lsof -i :17801 # Backend dev
lsof -i :17802 # Backend prod

# Or use ss
ss -tlnp | grep -E '5173|17801|17802'
```

### Stopping Services
```bash
# Kill by port
pkill -f "port 5173"
pkill -f "port 17801"

# Or use the stop script if available
./1_stop_all.sh
```

### Viewing Logs
```bash
# Development (running in terminal)
# Just check the terminal where you started the service

# Dienste
journalctl -u ai4artsed-backend -f
journalctl -u ai4artsed-gpu -f
```

## Troubleshooting

### Frontend not connecting to backend
- Check backend is running: `lsof -i :17801` (dev) or `lsof -i :17802` (prod)
- Check CORS configuration in backend
- Check frontend API base URL configuration

### Port already in use
```bash
# Find what's using the port
lsof -i :5173

# Kill the process
kill -9 <PID>
# Or
pkill -f "port 5173"
```

### Production deployment not working
1. Check if production backend is running
2. Check if frontend was built: `ls public/ai4artsed-frontend/dist`
3. Check nginx/reverse proxy configuration (if applicable)
4. Check backend logs for errors
5. Check Cloudflare tunnel status (if applicable)

### 404 errors
- **Frontend routes**: Check Vue Router configuration
- **API routes**: Check backend route definitions in `devserver/my_app/routes/`
- **Cloudflare tunnel**: Check tunnel configuration and DNS settings

### SwarmUI/ComfyUI not responding
```bash
# Check if ComfyUI is running
lsof -i :7821

# Check if SwarmUI is running
lsof -i :7801

# Restart if needed
```

## Architecture & Development

For technical details about the architecture, pipelines, and development patterns:

- **Architecture Details**: `docs/ARCHITECTURE PART 01-20.md` - Complete technical documentation
- **Current Tasks**: `docs/devserver_todos.md` - What needs to be done
- **Design Decisions**: `docs/DEVELOPMENT_DECISIONS.md` - Why things are the way they are

## Getting Help

- Check the documentation files above
- Review recent commits for context
- Check `devserver_todos.md` for known issues
