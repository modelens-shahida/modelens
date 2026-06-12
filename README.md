# ModelLens

ModelLens is an AI-powered visual catalog and model generation platform built for brands. The platform allows brands to manage creative assets, construct marketing campaigns, define workflow templates, generate synthetic characters, and execute similarity or full-text searches across their media libraries.

---

## 🚀 Tech Stack

### Frontend & API Gateway
* **Framework**: Next.js (App Router) & React
* **Styling**: Tailwind CSS & Framer Motion (for premium UI animations)
* **Authentication**: NextAuth.js (Session-based RBAC)
* **Search Clients**: Qdrant JS Client Rest, Supabase JS, and OpenAI Node SDK (for vector embeddings)

### Backend Services
* **Framework**: FastAPI (Python) & SQLAlchemy (Async engine)
* **Task Queue**: Celery & Redis (for asynchronous image validation, thumbnailing, and metadata parsing)
* **Database**: PostgreSQL with `pgvector` extension
* **Storage**: Local filesystem storage with AWS S3 compatibility layers

---

## 📁 Repository Structure

```tree
modelens/
├── app/                       # Next.js Frontend App Directory
│   ├── api/                   # Serverless Next.js API Routes (Supabase, Qdrant, OpenAI search)
│   │   └── auth/              # NextAuth dynamic handler
│   ├── auth/                  # Authentication page views (Login, Register)
│   ├── dashboard/             # Core Brand Dashboard pages (Campaigns, Jobs, Assets)
│   ├── search/                # Teammate Search UI test screen
│   └── upload/                # Teammate Upload UI test screen
├── backend/                   # FastAPI Backend
│   ├── alembic/               # Database migration versions and environment setup
│   ├── app/
│   │   ├── middleware/        # Authentication & Rate limiter middlewares
│   │   ├── models/            # SQLAlchemy Database Schemas & Session management
│   │   ├── routers/           # FastAPI routers (Assets, Auth, Brands, Campaigns, Jobs)
│   │   ├── services/          # Storage, Search, and ML Pipeline service handlers
│   │   └── worker.py          # Celery background tasks definition
│   ├── tests/                 # Isolated testing suite (SQLite aiosqlite integration)
│   └── seed_workflow_templates.py  # DB workflow template seeding utility
├── components/                # Reusable Next.js React Components
├── lib/                       # Qdrant & Supabase initialization scripts
├── docker-compose.yml         # Container configuration for Postgres, Redis, Celery, and Next.js
└── README.md                  # Project Documentation
```

---

## ✨ Key Features & Workflows

### 🛡️ Brand Role-Based Access Control (RBAC)
User scopes are strictly partitioned. Users are granted roles (`Owner`, `Admin`, `Editor`, `Viewer`) within specific brands. All asset queries, campaign mutations, and job submissions enforce access control filters relative to the brand ID and membership role.

### 🖼️ Automated Asset Processing Pipeline
When an asset is uploaded:
1. **MIME/Type Check**: Rejects unsupported files using Pillow.
2. **SHA-256 Deduplication**: Calculates checksum hash and links duplicate assets.
3. **EXIF Extraction**: Extracts metadata (resolution, camera settings, lighting).
4. **Thumbnails**: Automatically generates `256px` and `512px` thumbnail versions.
5. **JSONB Update**: Stores the schema details in the database `Asset.meta` column.

### 🔍 Search & Vector Engines
* **Full-Text Search (FTS)**: Multi-word query parsing matching titles, names, and tags.
* **Nearest-Neighbor Search (pgvector)**: Cosine similarity vector matching on tags.
* **Semantic & Hybrid Search (Qdrant & OpenAI)**: Text-embedding-3-large embeddings search for contextual results.

---

## 🛠️ Local Development Setup

### Prerequisite
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ensure daemon service is active)

### 1. Build and Launch Container Network
Run the docker compose setup in the root folder:
```bash
docker compose up --build -d
```
This boots:
* **PostgreSQL** (`localhost:5432`)
* **Redis** (`localhost:6379`)
* **FastAPI Backend API** (`localhost:8000`)
* **Celery Background Worker**
* **Next.js Frontend** (`localhost:3000`)
* **Flower Task Monitor** (`localhost:5555`)
* **MLflow Tracking Server** (`localhost:5000`)

### 2. Seeding Workflow Templates
Once the database container is online and migrations are complete, seed default workflow templates:
```bash
docker compose exec api python seed_workflow_templates.py
```

### 3. Run Automated Tests
FastAPI tests run in isolation using an in-memory SQLite setup. To execute the backend test suite:
```bash
cd backend
python -m pytest tests/ -v
```

---

## 🌐 VM Production Deployment

To deploy updates to the Azure VM environment:

1. **Access the VM**:
   ```bash
   ssh azureuser@20.197.8.77
   ```
2. **Fetch Source Updates**:
   ```bash
   cd ~/modelens
   git pull myrepo main
   ```
3. **Rebuild API & Worker Containers**:
   ```bash
   sudo docker compose build api worker
   ```
4. **Recreate the Containers**:
   ```bash
   sudo docker compose down
   sudo docker compose up -d
   ```
5. **Verify Database Seeding**:
   ```bash
   sudo docker compose exec api python seed_workflow_templates.py
   ```
