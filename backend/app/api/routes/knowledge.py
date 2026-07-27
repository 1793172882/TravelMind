"""HTTP controllers for user-owned RAG knowledge."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.dependencies import KnowledgeServiceDependency
from app.api.schemas.knowledge import (
    KnowledgeDocumentResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
)
from app.config import settings

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post(
    "/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    service: KnowledgeServiceDependency,
    file: Annotated[UploadFile, File(description="TXT、Markdown 或 PDF 文件")],
    title: Annotated[str | None, Form(max_length=255)] = None,
    source: Annotated[str | None, Form(max_length=500)] = None,
    city: Annotated[str | None, Form(max_length=100)] = None,
    category: Annotated[str | None, Form(max_length=100)] = None,
) -> KnowledgeDocumentResponse:
    """Index one upload in Chroma and save its directory entry in MySQL."""
    try:
        document = service.create_document(
            filename=file.filename or "document.txt",
            content_type=file.content_type or "application/octet-stream",
            content=file.file.read(settings.rag_max_file_bytes + 1),
            title=title,
            source=source,
            city=city,
            category=category,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return KnowledgeDocumentResponse.model_validate(document)


@router.get("/documents", response_model=list[KnowledgeDocumentResponse])
def list_documents(service: KnowledgeServiceDependency) -> list[KnowledgeDocumentResponse]:
    return [
        KnowledgeDocumentResponse.model_validate(document)
        for document in service.list_documents()
    ]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, service: KnowledgeServiceDependency) -> None:
    if not service.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Knowledge document not found")


@router.post("/search", response_model=list[KnowledgeSearchResult])
def search_knowledge(
    request: KnowledgeSearchRequest,
    service: KnowledgeServiceDependency,
) -> list[KnowledgeSearchResult]:
    return [
        KnowledgeSearchResult.model_validate(hit.as_dict())
        for hit in service.search(**request.model_dump())
    ]
