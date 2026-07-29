from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from enum import Enum
from os import path
from fastapi import Depends, UploadFile, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from app.settings import upload_dir, allow_type
from app.database import get_session
from app.service import ImageService
from app.schema import PageResponse


router = APIRouter()

   
@router.get('/', response_model=PageResponse)
async def get_images(
    page: int = Query(default=1, ge=1 ,description='页码'),
    page_size: int = Query(default=30, ge=1, le=100, description='每页条数'),
    session: AsyncSession = Depends(get_session)
):
    service = ImageService(session)
    return await service.list_paginated(page, page_size)

@router.post('/')
async def create_upload_file(file: UploadFile, session: AsyncSession = Depends(get_session)):
    if file.content_type not in allow_type.image:
        raise HTTPException(
            status_code=400,
            detail="仅支持 JPG, PNG, WebP 格式的图片"
        )
    
    filename = file.filename or 'default_name'
    content = await file.read()
    service = ImageService(session)
    image = await service.add(filename=filename, mime_type=str(file.content_type), content=content)
    if image is not None:
        return {
        "filename": file.filename, 
        "slug": image.slug,
        "content_type": file.content_type,
    }
    else:
        raise HTTPException(
            status_code=400,
            detail="上传失败"
        )

class TypeName(str, Enum):
    raw = 'raw'
    preivew = 'preview'

@router.get('/{slug}')
async def get_image(slug, _t: TypeName = TypeName.preivew, session: AsyncSession = Depends(get_session)):
    service = ImageService(session)
    image = await service.get_by_slug(slug)
    if image is not None:
        if _t == TypeName.raw:
            file_path = path.join(upload_dir.image_raw, slug)  
        elif _t == TypeName.preivew:
            slug, _ = path.splitext(slug)
            file_path = path.join(upload_dir.image_preview, slug + '.webp')
        return FileResponse(
                path=file_path, 
                media_type=image.mime_type, 
                headers={"Content-Disposition": "inline"}
            )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, 
        detail='Image not found'
        )

