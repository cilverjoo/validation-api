import traceback
from json import JSONDecodeError

import sentry_sdk
from fastapi import Request, APIRouter, status
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from app.models.validation import ValidationUrlModel
from app.services.validation import validate_by_url
from app.utils.logger import logger

INVALID_JSON_MESSAGE = "GT가 유효한 JSON 포맷이 아닙니다."
INVALID_URL_MESSAGE = "유효성검사 API의 URL이 잘못되었습니다."
MODULE_NOT_FOUND_MESSAGE = "URL에 매칭되는 유효성검사 로직이 존재하지 않습니다."
GENERAL_ERROR_MESSAGE = "유효성검사 중 에러가 발생했습니다. 자세한 내용은 DP팀에 문의해주세요."

router = APIRouter(
    prefix='/validation',
    tags=['validation']
)


@router.post('/{year}/{customer}/{project}/{version}', response_class=JSONResponse)
async def validate(request: Request, year, customer, project, version):
    try:
        parsed_url = ValidationUrlModel(year=year, customer=customer, project=project, version=version)
        gt = await request.json()

    except JSONDecodeError:
        logger.error(INVALID_JSON_MESSAGE)
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"message": INVALID_JSON_MESSAGE})
    except ValueError:
        logger.error(f"{INVALID_URL_MESSAGE} URL: {request.url}")
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"message": INVALID_URL_MESSAGE})

    try:
        validations = validate_by_url(gt, parsed_url)
        return JSONResponse(content=jsonable_encoder(validations))

    except ModuleNotFoundError:
        logger.error(f"{MODULE_NOT_FOUND_MESSAGE} URL: {request.url}")
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": MODULE_NOT_FOUND_MESSAGE})
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(error_detail)
        sentry_sdk.capture_exception(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": GENERAL_ERROR_MESSAGE}
        )
