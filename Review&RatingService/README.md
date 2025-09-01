# Review & Rating Service (MVP)

FastAPI service implementing in-memory reviews and rating aggregates.

OpenAPI reference: openapi/review_rating.yaml

## Endpoints

- POST /reviews
  - Body: ReviewCreateRequest { subjectId, subjectType: hotel|order|courier, rating (1..5), comment? }
  - Returns: Review

- GET /reviews?hotelId=...&limit=20
  - Returns: [Review] for subjectType=hotel only (per provided OpenAPI path)

- GET /ratings/aggregate?hotelId=...
  - Returns: { subjectId, subjectType, averageRating, ratingsCount, distribution }

## Run locally

1. Install dependencies:
   - python -m venv .venv && source .venv/bin/activate
   - pip install -r requirements.txt

2. Start server:
   - uvicorn main:app --host 0.0.0.0 --port 8105 --reload

3. Explore docs:
   - Swagger UI: http://localhost:8105/docs
   - OpenAPI JSON: http://localhost:8105/openapi.json

Notes:
- Storage is in-memory and resets on restart.
- CORS is permissive for local development; restrict in production.
