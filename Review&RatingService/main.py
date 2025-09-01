import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

# FastAPI app initialization with OpenAPI metadata and tags
app = FastAPI(
    title="Review & Rating Service API",
    description="Manages creation, retrieval, and moderation of reviews and ratings.",
    version="1.0.0",
    openapi_tags=[
        {"name": "Reviews", "description": "Endpoints for creating and listing reviews for a subject."},
        {"name": "Ratings", "description": "Endpoints for ratings and aggregations."},
        {"name": "Docs", "description": "Documentation and usage information."},
    ],
)

# Enable CORS for local development and potential frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# In-memory storage section
# =========================

# Each review is stored as a dict matching Review schema
_IN_MEMORY_REVIEWS: List[Dict] = []

# Aggregates are computed on-demand per request from _IN_MEMORY_REVIEWS


# =========================
# Pydantic Models (Schemas)
# =========================

class Review(BaseModel):
    """Review schema as per OpenAPI components.schemas.Review"""
    id: str = Field(..., description="Unique identifier for the review")
    subjectId: str = Field(..., description="ID of the subject being reviewed (e.g., hotel ID)")
    subjectType: str = Field(..., description="Type of the subject", regex="^(hotel|order|courier)$")
    rating: int = Field(..., ge=1, le=5, description="Rating value from 1 to 5")
    comment: Optional[str] = Field(None, description="Optional review comment")
    userId: str = Field(..., description="ID of the user who submitted the review")
    createdAt: datetime = Field(..., description="Creation timestamp in RFC3339 / ISO-8601 format")

    @validator("createdAt", pre=True)
    def ensure_datetime_with_tz(cls, v):
        # Ensure timezone-aware datetime
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError("createdAt must be a datetime or ISO string")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt


class ReviewCreateRequest(BaseModel):
    """Request body for creating a review, per OpenAPI components.schemas.ReviewCreateRequest"""
    subjectId: str = Field(..., description="ID of the subject being reviewed (e.g., hotel ID)")
    subjectType: str = Field(..., description="Type of the subject", regex="^(hotel|order|courier)$")
    rating: int = Field(..., ge=1, le=5, description="Rating value from 1 to 5")
    comment: Optional[str] = Field(None, description="Optional review comment")
    # Not in spec but useful; if not provided, we'll simulate anonymous user
    userId: Optional[str] = Field(None, description="ID of the user submitting the review")


class RatingAggregate(BaseModel):
    """Aggregate rating result for a given subject (e.g., hotel)."""
    subjectId: str = Field(..., description="ID of the subject being aggregated (e.g., hotel ID)")
    subjectType: str = Field(..., description="Type of the subject", regex="^(hotel|order|courier)$")
    averageRating: float = Field(..., description="Average rating for the subject")
    ratingsCount: int = Field(..., description="Number of ratings considered for the aggregate")
    distribution: Dict[int, int] = Field(
        ..., description="Distribution of ratings; keys are 1..5 and values are counts"
    )


# =========================
# Helper functions
# =========================

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_id() -> str:
    return str(uuid.uuid4())


def _to_review_dict(review: Review) -> Dict:
    # Convert model to JSON-serializable dict with ISO timestamp
    data = review.dict()
    if isinstance(data.get("createdAt"), datetime):
        data["createdAt"] = data["createdAt"].isoformat()
    return data


# =========================
# Routes
# =========================

# PUBLIC_INTERFACE
@app.get(
    "/reviews",
    response_model=List[Review],
    summary="List reviews for a hotel",
    description="Returns a list of reviews filtered by hotelId (mapped to subjectId with subjectType=hotel).",
    tags=["Reviews"],
)
def list_reviews(
    hotelId: str = Query(..., description="Hotel ID to filter reviews for"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of reviews to return"),
):
    """List reviews for a given hotel ID.

    Parameters:
    - hotelId: The hotel identifier used to filter reviews (maps to subjectId for subjectType 'hotel')
    - limit: Maximum number of reviews to return (1..100)

    Returns:
    - List[Review]: Array of review objects for the specified hotel
    """
    # Filter by subjectId and subjectType=hotel
    filtered = [
        Review(**r) if not isinstance(r, Review) else r
        for r in _IN_MEMORY_REVIEWS
        if r["subjectId"] == hotelId and r["subjectType"] == "hotel"
    ]
    # Sort by createdAt descending for consistency
    filtered.sort(key=lambda r: r.createdAt if isinstance(r, Review) else datetime.fromisoformat(r["createdAt"]), reverse=True)
    # Truncate to limit
    result = filtered[:limit]
    # Ensure Pydantic models returned
    return [r if isinstance(r, Review) else Review(**r) for r in result]


# PUBLIC_INTERFACE
@app.post(
    "/reviews",
    response_model=Review,
    status_code=status.HTTP_201_CREATED,
    summary="Create review",
    description="Create a new review for a subject (hotel/order/courier). For GET /reviews compatibility, only hotel reviews are returned there.",
    tags=["Reviews"],
)
def create_review(payload: ReviewCreateRequest):
    """Create a new review.

    Body:
    - ReviewCreateRequest: Contains subjectId, subjectType (hotel|order|courier), rating (1..5), and optional comment

    Returns:
    - Review: The created review object with id, userId (if provided or generated), and createdAt timestamps
    """
    # Simple in-memory creation; in real service, authenticate and derive userId
    user_id = payload.userId or "anonymous-user"
    review = Review(
        id=_generate_id(),
        subjectId=payload.subjectId,
        subjectType=payload.subjectType,
        rating=payload.rating,
        comment=payload.comment,
        userId=user_id,
        createdAt=_now_utc(),
    )
    _IN_MEMORY_REVIEWS.append(_to_review_dict(review))
    return review


# PUBLIC_INTERFACE
@app.get(
    "/ratings/aggregate",
    response_model=RatingAggregate,
    summary="Get aggregate rating for a hotel",
    description="Compute and return the rating aggregation for a given hotelId (subjectType=hotel).",
    tags=["Ratings"],
)
def get_rating_aggregate(
    hotelId: str = Query(..., description="Hotel ID to aggregate ratings for"),
):
    """Get aggregate rating for a given hotel.

    Parameters:
    - hotelId: The hotel identifier used to compute aggregation (maps to subjectId with subjectType 'hotel')

    Returns:
    - RatingAggregate: Average rating, total count, and distribution across 1..5
    """
    subset = [
        r for r in _IN_MEMORY_REVIEWS
        if r["subjectId"] == hotelId and r["subjectType"] == "hotel"
    ]

    distribution = {i: 0 for i in range(1, 6)}
    total = 0
    sum_ratings = 0
    for r in subset:
        rating = int(r["rating"])
        if rating < 1 or rating > 5:
            continue  # Skip invalid entries (shouldn't happen due to validation)
        distribution[rating] += 1
        sum_ratings += rating
        total += 1

    average = float(sum_ratings) / total if total > 0 else 0.0

    aggregate = RatingAggregate(
        subjectId=hotelId,
        subjectType="hotel",
        averageRating=round(average, 2),
        ratingsCount=total,
        distribution=distribution,
    )
    return aggregate


# PUBLIC_INTERFACE
@app.get(
    "/docs/websocket-usage-note",
    tags=["Docs"],
    summary="WebSocket and real-time note",
    description="This MVP does not include WebSockets. For real-time updates, clients should poll GET /ratings/aggregate periodically.",
)
def docs_ws_note():
    """Simple docs note to clarify real-time behavior in this MVP."""
    return {
        "message": "No WebSocket endpoint in MVP. Use polling on GET /ratings/aggregate for near real-time updates."
    }


# Root route (optional convenience)
@app.get("/", tags=["Docs"], summary="Service info")
def root():
    return {
        "service": "Review & Rating Service",
        "version": "1.0.0",
        "endpoints": ["/reviews [GET, POST]", "/ratings/aggregate [GET]"],
    }


if __name__ == "__main__":
    import uvicorn
    # Run development server
    uvicorn.run("main:app", host="0.0.0.0", port=8105, reload=True)
