# UI Migration: Standalone HTML → Vite React

**Date:** 2026-10-23

## Changes Made

### 1. Backend Updates (`src/camerainspection/api/app.py`)
- Updated `get_ui_index_path()` to point to `frontend/dist/index.html` instead of `ui/index.html`
- Added static file mounting for `/assets` to serve Vite build output
- Updated error message to guide users to run `npm run build` if frontend is missing

### 2. Frontend Configuration (`frontend/vite.config.ts`)
- Added dev server proxy configuration for API routes (`/api`, `/storage`, `/data`, `/configs`)
- Set base path to `/` for production builds
- Configured server port to 5173 for local development

### 3. Removed
- Deleted entire `ui/` directory containing the standalone `index.html` (~3700 lines of embedded JS/CSS)

## How to Use

### Development Mode
```bash
# Terminal 1: Run backend API
python -m camerainspection.main --host 127.0.0.1 --port 8000

# Terminal 2: Run Vite dev server (with HMR)
cd frontend
npm run dev
```

The Vite dev server will proxy API requests to the backend automatically.

### Production Mode
```bash
# Build frontend first
cd frontend
npm run build

# Run backend (will serve built frontend at root)
python -m camerainspection.main --host 127.0.0.1 --port 8000
```

Navigate to `http://127.0.0.1:8000/` to see the React frontend served by FastAPI.

## Architecture

```
┌─────────────────────────────────────────┐
│  FastAPI Backend (Port 8000)            │
│  ├─ / → frontend/dist/index.html       │
│  ├─ /assets → frontend/dist/assets/*   │
│  ├─ /api/v1/* → API endpoints          │
│  ├─ /storage → storage/ directory      │
│  ├─ /data → data/ directory            │
│  └─ /configs → configs/ directory      │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  React Frontend (Vite)                  │
│  ├─ App.tsx (main router)              │
│  ├─ components/                        │
│  │   ├─ Header.tsx                     │
│  │   ├─ LiveLine.tsx                   │
│  │   └─ DefectGallery.tsx              │
│  └─ API calls use fetch to /api/v1/*   │
└─────────────────────────────────────────┘
```

## Next Steps

The current frontend has basic components. You'll need to:

1. **Port remaining features from the old HTML:**
   - Quality Trends (charts with Recharts)
   - System Health monitoring
   - Review Queue
   - Settings panel
   - Camera management
   - Rework Bench
   - Audit Log
   - Shadow Mode analytics
   - SPC charts
   - ROI editor
   - Andon board

2. **Set up API integration:**
   - Create API client utility
   - Add React Query or SWR for data fetching
   - Implement authentication (X-API-Key header)
   - Handle loading states and errors

3. **Enhance the existing components:**
   - Add real API calls to LiveLine and DefectGallery
   - Implement real-time updates (polling or WebSocket)
   - Add proper TypeScript interfaces for API responses

## Files Changed
- `src/camerainspection/api/app.py` (backend routing)
- `frontend/vite.config.ts` (dev proxy config)
- Deleted: `ui/index.html` and entire `ui/` directory
