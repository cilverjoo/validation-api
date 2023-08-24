from typing import List

import cv2
import numpy as np

from app.models.sensor_fusion import SensorFusionModel


def project_pinhole_points(values: SensorFusionModel) -> List:
    results = []

    rotation_vector = rotation_matrix_to_rodrigues_rotation_vector(values.converted_rotation_matrix)
    for annotation in values.instances:
        corner_3d = lidar_annotation_to_3d_bbox(annotation)
        object_points = np.array([corner_3d], dtype=np.float32)
        point_2d, _ = cv2.projectPoints(objectPoints=object_points,
                                        rvec=rotation_vector, tvec=values.translations,
                                        cameraMatrix=values.intrinsicMatrix,
                                        distCoeffs=values.distortionCoefficients)
        point_2d = point_2d.astype(np.int32).reshape(8, 2)
        results.append(point_2d.tolist())

    return results


def project_fisheye_points(values: SensorFusionModel) -> List:
    results = []

    rotation_vector = rotation_matrix_to_rodrigues_rotation_vector(values.converted_rotation_matrix)
    for annotation in values.instances:
        corner_3d = lidar_annotation_to_3d_bbox(annotation)
        object_points = np.array([corner_3d], dtype=np.float32)
        point_2d, _ = cv2.fisheye.projectPoints(objectPoints=object_points,
                                                rvec=rotation_vector, tvec=values.translations,
                                                K=values.intrinsicMatrix, D=values.distortionCoefficients)
        results.append(point_2d[0].tolist())

    return results
