from datetime import date
from typing import List

from fastapi import APIRouter, Depends

from .core.controllers.agency.product_management_controller import (
    CaseRecordsController,
)
from .core.controllers.manage_cache_dependency import manage_request_state
from .core.schemas.agency.case_records import (
    CaseRecordCreate,
)

_case_router = APIRouter(
    prefix="/v1/product_management",
    tags=["product_management"],
    dependencies=[Depends(manage_request_state)],
)


@_case_router.post("/case")
async def create_case_record(
    request: CaseRecordCreate,
    controller: CaseRecordsController = Depends(),
):
    return await controller.create_case_records(request)
