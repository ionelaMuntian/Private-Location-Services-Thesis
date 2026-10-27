# Privacy-Preserving Location-Based Services with Homomorphic Encryption

This repository contains the implementation for the bachelor's thesis *Using Homomorphic Encryption for Privacy-Preserving Location-Based Services* (Technical University of Cluj-Napoca).

Location-based services normally require users to hand their exact coordinates to a remote server. This project explores an alternative: the user's location is encrypted on a trusted client, and an **untrusted service provider computes directly on the ciphertexts** using fully homomorphic encryption (FHE). The provider returns encrypted results that only the client can decrypt, so it never learns where the user is.

## Features

| Service | What it does | FHE technology |
|---|---|---|
| **Nearest-K POI search** | Finds the *k* closest points of interest of a chosen category (e.g. pharmacies, bookshops) to the user's encrypted location. | Concrete (TFHE) and OpenFHE (CKKS), with a plaintext baseline |
| **Company location compliance** | Lets a company check whether an employee is at home, at the office or inside the country without either party revealing the raw coordinates. Bounding-box margins are evaluated homomorphically under a two-party (user + company) key. | OpenFHE multiparty CKKS |
| **Impossible-travel detection** | Risk-based authentication: flags suspicious logins by comparing consecutive login events, with inference on encrypted features. | Concrete ML (quantized XGBoost) |
| **Benchmarking** | Runs the same POI query across all schemes and records latency per step (encryption, key upload, server evaluation, decryption). | — |

## Architecture

```
┌──────────────┐  HTTP   ┌──────────────────────────┐  gRPC   ┌──────────────────────────┐
│   Frontend   │ ──────► │       Client app         │ ──────► │  Service provider app    │
│ React + Vite │         │  (trusted side)          │         │  (untrusted side)        │
└──────────────┘         │  • key generation        │         │  • homomorphic evaluation│
                         │  • encryption/decryption │         │  • POI repository        │
                         │  • auth, users, company  │         │  • FHE model inference   │
                         └────────────┬─────────────┘         └────────────┬─────────────┘
                                      │                                    │
                     PostgreSQL (auth, users, company)            PostGIS (POI dataset)
```

- **Client app** (`client_app/`): FastAPI service that owns all secret keys. It encrypts queries, uploads evaluation keys to the provider over streaming gRPC, decrypts results, and manages authentication, users and company data.
- **Service provider app** (`service_provider_app/`): FastAPI + gRPC server that holds the POI database and the encrypted ML model. It only ever receives ciphertexts and public/evaluation keys.
- **Frontend** (`frontend/`): React interface for POI search, location sharing, the company admin dashboard, anomaly detection and benchmark statistics.
- **gRPC contract** (`proto/service_provider.proto`): generic request gateway plus chunked key-upload streams for Concrete and OpenFHE keys.
- **Training notebook** (`notebooks/impossible_travel_model.ipynb`): dataset analysis, feature engineering, training and FHE compilation of the impossible-travel model.

## Tech stack

**Cryptography:** OpenFHE (CKKS, multiparty), Concrete, Concrete ML
**Backend:** Python 3.12, FastAPI, gRPC / Protocol Buffers, Pydantic
**Data:** PostgreSQL 16, PostGIS, OpenStreetMap POI data
**ML:** XGBoost, scikit-learn, imbalanced-learn (SMOTE)
**Frontend:** React 19, Vite, React Router, Recharts
**Infrastructure:** Docker, Docker Compose

## Repository structure

```
.
├── client_app/              # Trusted client: keys, encryption, auth, company logic
│   ├── app/
│   │   ├── core/            # OpenFHE / Concrete runtimes, config, metrics
│   │   ├── infrastructure/  # Database and gRPC clients
│   │   └── modules/         # auth, poi_search, company, anomaly_detection
│   └── tools/               # Concrete circuit compilation for distance computation
├── service_provider_app/    # Untrusted server: homomorphic evaluation
│   └── app/
│       ├── core/            # OpenFHE / Concrete server runtimes
│       └── modules/         # poi_search engines, company compliance, anomaly_detection
├── frontend/                # React user interface
├── proto/                   # gRPC service definition
├── notebooks/               # Model training and FHE compilation
├── datasets/                # POI dataset (Cluj-Napoca, OpenStreetMap)
└── compose.yaml             # Full local deployment
```

## Getting started

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for the frontend)

### 1. Configure environment variables

Both backend services read their settings from a `.env` file:

- `client_app/.env`
- `service_provider_app/.env`

These hold the database connection settings (host, port, name, user, password) for each service. Make sure the passwords match those configured for the database containers in `compose.yaml`.

### 2. Start the backend

```bash
docker compose up --build
```

This starts four databases, the service provider and the client app:

| Service | Port |
|---|---|
| Client app (REST API) | `8000` |
| Service provider (REST / gRPC) | `8001` / `50051` |
| PostGIS (POI data) | `5432` |
| PostgreSQL (auth / users / company) | `5433` / `5434` / `5435` |

Interactive API documentation is available at `http://localhost:8000/docs` once the client app is running.

### 3. Load the POI dataset

The service provider queries the table `thesis.poi` in the `osm_ro` database. Import `datasets/poi.csv` (columns `id, name, category, lat, lon, lat_m, lon_m, geom, city`, with `geom` in EPSG:3857) into that table before running POI searches.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The interface is served at `http://localhost:5173`.

### 5. (Optional) Retrain the anomaly detection model

The trained plaintext and FHE models are already included under `service_provider_app/app/modules/anomaly_detection/models/`. To retrain them, place the RBA dataset (`rba-dataset.csv`) in `datasets/` and start the Jupyter environment:

```bash
docker compose --profile training up jupyter_training
```

JupyterLab is then available at `http://localhost:8888`. Running the notebook regenerates the model artifacts, including the FHE client/server bundles.

## Threat model

The service provider is treated as **honest-but-curious**: it executes the protocol correctly but may try to learn as much as possible from the data it receives. All location coordinates and model features leave the client only in encrypted form, and secret keys never leave the client app. The POI-search request schemas additionally reject encrypted queries that contain plaintext coordinate fields.

## Author

**Mariana-Ionela Muntian**, Technical University of Cluj-Napoca
