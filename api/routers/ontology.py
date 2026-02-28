"""Ontology constraints API router."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import OntologyConstraint
from api.schemas import OntologyConstraintRead

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/constraints", response_model=list[OntologyConstraintRead])
async def list_constraints(
    limit: int = Query(100, ge=1, le=500),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List ontology constraints (Auger-style hard rules)."""
    q = select(OntologyConstraint).order_by(OntologyConstraint.id).limit(limit)
    if entity_type:
        q = q.where(OntologyConstraint.entity_type == entity_type)
    if entity_id:
        q = q.where(OntologyConstraint.entity_id == entity_id)
    result = await db.execute(q)
    constraints = result.scalars().all()
    return [OntologyConstraintRead.model_validate(c) for c in constraints]
