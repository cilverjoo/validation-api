import traceback
from json import JSONDecodeError

import sentry_sdk
from fastapi import Request, APIRouter, status
from fastapi.responses import JSONResponse

from app.models.errors import SensorFusionValueError
from app.models.sensor_fusion import SensorFusionModel, CameraType
from app.sensor_fusion.project_points import project_fisheye_points, project_pinhole_points, project_cylindrical_points
from app.utils.logger import logger

INVALID_CAMERA_TYPE_MESSAGE = "카메라 타입이 유효하지 않습니다. {}"
INVALID_JSON_MESSAGE = "GT가 유효한 JSON 포맷이 아닙니다."
SENSOR_FUSION_ERROR_MESSAGE = "센서 퓨전 API에 문제가 발생했습니다. 자세한 내용은 개발팀에 문의해주세요."


router = APIRouter(
    prefix='/sensor-fusion',
    tags=['sensor-fusion']
)


@router.post('/{camera_type}', response_class=JSONResponse)
async def convert_sensor_fusion_points(request: Request, camera_type: str):
    try:
        gt = await request.json()
        sensor_fusion_values = SensorFusionModel(**gt)

        if camera_type == CameraType.pinhole.value:
            sensor_fusion_points = project_pinhole_points(sensor_fusion_values)
        elif camera_type == CameraType.fisheye.value:
            sensor_fusion_points = project_fisheye_points(sensor_fusion_values)
        else:
            sensor_fusion_points = project_cylindrical_points(sensor_fusion_values)

        return JSONResponse(sensor_fusion_points)

    except JSONDecodeError:
        logger.error(INVALID_JSON_MESSAGE)
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"message": INVALID_JSON_MESSAGE})

    except SensorFusionValueError as e:
        logger.error(f"{e}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"message": f"{e}"}
        )

    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(error_detail)
        sentry_sdk.capture_exception(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": SENSOR_FUSION_ERROR_MESSAGE}
        )
