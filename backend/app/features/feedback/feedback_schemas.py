"""Request bodies for rating an order."""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.shared.validation import MAX_ORDER_LINES, blank_to_none


class RatingIn(BaseModel):
    menu_item_id: int
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=300)

    _clean_comment = field_validator("comment")(blank_to_none)


class FeedbackIn(BaseModel):
    ratings: List[RatingIn] = Field(min_length=1, max_length=MAX_ORDER_LINES)
    allow_public: bool = False  # "OK to show my name and review on the website"

    @field_validator("ratings")
    @classmethod
    def one_rating_per_item(cls, v: List[RatingIn]) -> List[RatingIn]:
        if len({r.menu_item_id for r in v}) != len(v):
            raise ValueError("Rate each item only once")
        return v
