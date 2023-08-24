from enum import Enum
from typing import List, Union

import numpy as np
from pydantic import BaseModel, validator, root_validator

from app.models.errors import SensorFusionValueError

class CameraType(str, Enum):
    pinhole = "pinhole"
    fisheye = "fisheye"
    cylinder = "cylinder"


class AnnotationModel(BaseModel):
    position: List[float]
    geometry: List[float]
    rotation: List[float]


class SensorFusionModel(BaseModel):
    instances: List[AnnotationModel]
    rotations: Union[List[float], List[List[float]]] = None
    translations: List[float] = None
    intrinsicCameraParameters: List[float] = None
    intrinsicMatrix: List[float] = None
    distortionCoefficients: List[float] = None
    isInverseMatrix: bool = False
    imageWidth: int = None
    imageHeight: int = None
    converted_rotation_matrix: List[List[float]] = None

    @root_validator  # called after all the other validators for the fields have been run
    def set_converted_rotation_matrix(cls, values):
        """
        Labelers 툴 셋팅시: FE "rotations", "rotationsMatrix" -> DP "rotations"로 전달
        META 폴더 셋팅시: BE "rotations", "rotation_matrix" -> FE "rotations", "rotationsMatrix" -> DP "rotations"로 전달
        ::values.rotations:: euler radians 1X3 배열 | quaternion [w, x, y, z] 1X4 배열 | rotation matrix 3X3 배열
        """
        rotations = np.array(values.get('rotations'), dtype=np.float32)
        values['converted_rotation_matrix'] = sensor_fusion_model_rotations_to_rotation_matrix(rotations)
        return values

    @validator('intrinsicCameraParameters', always=True)
    def validate_intrinsic_camera_parameters(cls, value):
        if not value:
            raise SensorFusionValueError(f'intrinsicCameraParameters 값이 존재하지 않습니다.')

        if len(value) == 8:
            return value
        raise SensorFusionValueError(
            f'intrinsicCameraParameters 값은 8X1의 리스트 여야 합니다.\nintrinsicCameraParameters : {value}')

    @validator('distortionCoefficients', always=True)
    def set_distortion_coefficients(cls, v, values):
        intrinsic_params = values.get('intrinsicCameraParameters')
        if intrinsic_params:
            _, _, _, _, k1, k2, p1, p2 = intrinsic_params
            return np.array([k1, k2, p1, p2], dtype=np.float32)

    @validator('translations', always=True)
    def validate_translation_vector(cls, value):
        if not value:
            raise SensorFusionValueError(f'translations 값이 존재하지 않습니다.')

        if len(value) == 3:
            return np.array(value, dtype=np.float32)
        raise SensorFusionValueError(f'translations 값은 1X3의 리스트 여야 합니다.\ntranslations: {value}')

    @validator('intrinsicMatrix', always=True)
    def validate_intrinsic_matrix(cls, v, values):
        intrinsic_params = values.get('intrinsicCameraParameters')
        if intrinsic_params:
            fx, fy, cx, cy, _, _, _, _ = intrinsic_params
            return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float32)

    @validator('rotations', always=True)
    def validate_rotations(cls, value):
        if not value:
            raise SensorFusionValueError(f'rotations 값이 존재하지 않습니다.')

        value = np.array(value, dtype=np.float32)
        if is_euler_shape(value):
            if is_radian(value):
                return value
            else:
                raise SensorFusionValueError(f'euler rotations 값은 -2 * pi ~ 2 * pi의 범위여야 합니다.\nrotations : {value}')

        elif is_quaternion_shape(value):
            return value

        elif is_rotation_matrix_shape(value):
            return value

        raise SensorFusionValueError(f'rotations 값은 1X3, 1X4, 3X3의 리스트 여야 합니다.\nrotations : {value}')
