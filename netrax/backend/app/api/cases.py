"""
Cases API — CRUD operations for investigation cases.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.case import Case, CaseStatus
from app.models.document import Document
from app.schemas.case import CaseCreate, CaseUpdate, CaseResponse, CaseListResponse

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(data: CaseCreate, db: AsyncSession = Depends(get_db)):
    """Create a new investigation case."""
    # Check for duplicate case number
    existing = await db.execute(
        select(Case).where(Case.case_number == data.case_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case with number '{data.case_number}' already exists",
        )

    try:
        case_status = CaseStatus(data.status)
    except ValueError:
        case_status = CaseStatus.OPEN

    case = Case(
        case_number=data.case_number,
        title=data.title,
        description=data.description,
        status=case_status,
    )
    db.add(case)
    await db.flush()

    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        status=case.status.value,
        document_count=0,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("", response_model=CaseListResponse)
async def list_cases(db: AsyncSession = Depends(get_db)):
    """List all investigation cases."""
    result = await db.execute(
        select(Case).order_by(Case.created_at.desc())
    )
    cases = result.scalars().all()

    case_responses = []
    for case in cases:
        # Count documents per case
        doc_count_result = await db.execute(
            select(func.count(Document.id)).where(Document.case_id == case.id)
        )
        doc_count = doc_count_result.scalar() or 0

        case_responses.append(CaseResponse(
            id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            status=case.status.value,
            document_count=doc_count,
            created_at=case.created_at,
            updated_at=case.updated_at,
        ))

    return CaseListResponse(cases=case_responses, total=len(case_responses))


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)):
    """Get case details by ID."""
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    doc_count_result = await db.execute(
        select(func.count(Document.id)).where(Document.case_id == case.id)
    )
    doc_count = doc_count_result.scalar() or 0

    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        status=case.status.value,
        document_count=doc_count,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(case_id: str, data: CaseUpdate, db: AsyncSession = Depends(get_db)):
    """Update case details."""
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if data.title is not None:
        case.title = data.title
    if data.description is not None:
        case.description = data.description
    if data.status is not None:
        try:
            case.status = CaseStatus(data.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")

    await db.flush()

    doc_count_result = await db.execute(
        select(func.count(Document.id)).where(Document.case_id == case.id)
    )
    doc_count = doc_count_result.scalar() or 0

    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        status=case.status.value,
        document_count=doc_count,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )
