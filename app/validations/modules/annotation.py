import math
from collections import Counter
from typing import List

from shapely.geometry import Polygon

from app.models.validation import AnnotationError
from app.validations.utils.config import AnnotationType
from app.validations.utils.shape import get_wh, is_clockwise_order, has_outside_point, outside_points_to_inside_points
from app.validations.modules import AnnotationValidator


class AnnotationBboxValidator(AnnotationValidator):
    def is_checkable(self, annotation):
        return annotation['type'] == 'bbox'

    def _validate_point_count(self, errors, annotation):
        # Bbox의 points는 4점이어야 함
        if len(annotation['points']) != 4:
            errors.append(self.create_error(annotation=annotation, error_code='points_length_error',
                                            error_detail=f'points count : {len(annotation["points"])}'))

    def _validate_not_rotated(self, errors, annotation):
        # Bbox는 직사각형이어야 함
        x_coordinates, y_coordinates = set(), set()
        for point in annotation['points']:
            x_coordinates.add(point[0])
            y_coordinates.add(point[1])
        if len(x_coordinates) != 2 or len(y_coordinates) != 2:
            errors.append(self.create_error(annotation=annotation, error_code='points_location_error',
                                            error_detail=f'points list : {annotation["points"]}'))

    def _validate_duplicated(self, errors, annotation):
        unique_points = set()
        for point in annotation['points']:
            unique_points.add(f'{point[0]}_{point[1]}')

        if len(unique_points) != len(annotation['points']):
            errors.append(self.create_error(annotation=annotation, error_code='points_duplicated',
                                            error_detail=f'{annotation["points"]}'))

    def _validate_bbox_bounds_area(self, errors, annotation):
        w, h = get_wh(annotation["points"])
        area = w * h
        if area == 0:
            errors.append(self.create_error(annotation=annotation,
                                            error_code=f'bounds area 0',
                                            error_detail=f'points: {annotation["points"]}'))

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        self._validate_point_count(errors, annotation)
        self._validate_not_rotated(errors, annotation)
        self._validate_duplicated(errors, annotation)
        self._validate_bbox_bounds_area(errors, annotation)

        return errors


class AnnotationObboxValidator(AnnotationValidator):
    def is_checkable(self, annotation):
        return annotation['type'] == 'obbox'

    def _validate_point_count(self, errors, annotation):
        # Bbox의 points는 4점이어야 함
        if len(annotation['points']) != 4:
            errors.append(self.create_error(annotation=annotation, error_code='points_length_error',
                                            error_detail=f'points count : {len(annotation["points"])}'))

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        self._validate_point_count(errors, annotation)

        return errors


class AnnotationOBboxV2Validator(AnnotationValidator):
    def is_checkable(self, annotation):
        return annotation['type'] == "obbox_v2"

    def _validate_xywh_count(self, errors, annotation):
        # Obbox_v2의 rect는 x, y, w, h 4개의 정보를 가지고 있어야함.
        if len(annotation['rect']) != 4:
            errors.append(self.create_error(annotation=annotation, error_code='rectangle_length_error',
                                            error_detail=f'rectangle count: {len(annotation["points"])}'))

    def _validate_positive_width_height(self, errors, annotation):
        _, _, width, height = annotation["rect"]
        if width <= 0 or height <= 0:
            errors.append(self.create_error(annotation=annotation, error_code='rectangle_size_negative_values_error',
                                            error_detail=f'width: {width} height: {height}'))

    def _validate_degree_range(self, errors, annotation):
        degree = annotation["degree"]
        if (degree > 270) or (degree < -89.5):
            errors.append(self.create_error(annotation=annotation, error_code='degree_range_error',
                                            error_detail=f'degree range is not valid: {degree}'))

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        self._validate_xywh_count(errors, annotation)
        self._validate_positive_width_height(errors, annotation)
        self._validate_degree_range(errors, annotation)
        return errors


class AnnotationPolylineValidator(AnnotationValidator):
    def __init__(self, point_length=None, minimum_point_length=2, maximum_point_length=None, is_warning=False):
        super().__init__(is_warning)
        self.point_length = point_length
        self.minimum_point_length = minimum_point_length
        self.maximum_point_length = maximum_point_length

    def is_checkable(self, annotation):
        return annotation['type'] == 'polyline'

    def _validate_minimum_point_length(self, errors, annotation):
        is_warning = False if self.minimum_point_length == 2 else self.is_warning
        if len(annotation['points']) < self.minimum_point_length:
            errors.append(self.create_error(annotation=annotation,
                                            error_code=f'below_the_limit_of_minimum_polygon_length: {self.minimum_point_length}',
                                            error_detail=f'point count : {len(annotation["points"])}',
                                            is_warning=is_warning))

    def _validate_maximum_point_length(self, errors, annotation):
        if self.maximum_point_length is None:
            return

        if len(annotation['points']) > self.maximum_point_length:
            errors.append(self.create_error(annotation=annotation,
                                            error_code=f'exceeding_limit_of_maximum_polygon_length: {self.maximum_point_length}',
                                            error_detail=f'point count : {len(annotation["points"])}'))

    def _validate_point_length(self, errors, annotation):
        if self.point_length is None:
            return

        if len(annotation['points']) != self.point_length:
            errors.append(self.create_error(annotation=annotation, error_code='polyline_length_error',
                                            error_detail=f'point count : {len(annotation["points"])}'))

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        self._validate_point_length(errors, annotation)
        self._validate_minimum_point_length(errors, annotation)
        self._validate_maximum_point_length(errors, annotation)

        return errors


class AnnotationKeypointValidator(AnnotationValidator):
    def __init__(self, length=None, max_length=None, start_key='0', is_warning=False):
        super().__init__(is_warning)
        self.length = length
        self.max_length = max_length
        self.start_key = start_key

    def is_checkable(self, annotation):
        """
        eimmo-sdk==v1.0.2 라벨러스에서 keypoint프로젝트의 경우, 백엔드에서는 AnnotationType.landmark를 사용
        그러나 산출물 내보내기시 인스턴스의 "type" key에 "landmark"가 아닌 "keypoint"로 보이도록 강제되어있음
        """
        return annotation['type'] in [AnnotationType.keypoint.value, 'keypoint']

    def _get_max_key(self, keypoints):
        keys = keypoints.keys()

        return str(max(int(key) for key in keys))

    def _validate_point_length(self, errors, annotation):
        if self.length is None:
            return

        if len(annotation['keypoints']) != self.length:
            errors.append(self.create_error(annotation=annotation, error_code='length_error',
                                            error_detail=f'keypoints count : {len(annotation["keypoints"])}'))

    def _validate_max_length(self, errors, annotation):
        if self.max_length is None:
            return

        if len(annotation['keypoints']) > self.max_length:
            errors.append(self.create_error(annotation=annotation, error_code='length_error',
                                            error_detail=f'keypoints count : {len(annotation["keypoints"])}'))

    def _validate_max_key(self, errors, annotation):
        if self.max_length is None and self.length is None:
            return

        expected_max_key = str(self.max_length or self.length + int(self.start_key))
        max_key = self._get_max_key(annotation['keypoints'])

        if int(max_key) > int(expected_max_key):
            errors.append(self.create_error(annotation=annotation, error_code='max_key_number_error',
                                            error_detail=f'max key : {max_key}'))

    def _validate_key_type(self, errors, annotation):
        for key in annotation['keypoints'].keys():
            if isinstance(key, str) == False:
                errors.append(
                    self.create_error(annotation=annotation, error_code='key_is_not_str', error_detail=f'{type(key)}'))
                break

        for key in annotation['invisible_keys']:
            if isinstance(key, str) == False:
                errors.append(self.create_error(annotation=annotation, error_code='invisible_key_is_not_str',
                                                error_detail=f'{type(key)}'))
                break

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        self._validate_point_length(errors, annotation)
        self._validate_max_length(errors, annotation)
        self._validate_max_key(errors, annotation)
        self._validate_key_type(errors, annotation)

        return errors


class AnnotationPolygonValidator(AnnotationValidator):
    def __init__(self, point_length=None, minimum_point_length=3, maximum_point_length=None, is_warning=False):
        super().__init__(is_warning)
        self.point_length = point_length
        self.minimum_point_length = minimum_point_length
        self.maximum_point_length = maximum_point_length

    def is_checkable(self, annotation):
        return annotation['type'] == 'polygon'

    def _validate_minimum_point_length(self, errors, annotation):
        if self.minimum_point_length is None:
            return

        if len(annotation['points']) < self.minimum_point_length:
            errors.append(self.create_error(annotation=annotation,
                                            error_code=f'below_the_limit_of_minimum_polygon_length: {self.minimum_point_length}',
                                            error_detail=f'point count : {len(annotation["points"])}'))

    def _validate_maximum_point_length(self, errors, annotation):
        if self.maximum_point_length is None:
            return

        if len(annotation['points']) > self.maximum_point_length:
            errors.append(self.create_error(annotation=annotation,
                                            error_code=f'exceeding_limit_of_maximum_polygon_length: {self.maximum_point_length}',
                                            error_detail=f'point count : {len(annotation["points"])}'))

    def _validate_point_length(self, errors, annotation):
        if self.point_length is None:
            return

        if len(annotation['points']) != self.point_length:
            errors.append(self.create_error(annotation=annotation, error_code='polyline_length_error',
                                            error_detail=f'point count : {len(annotation["points"])}'))

    def _validate_polygon_bounds_area(self, errors, annotation):
        w, h = get_wh(annotation["points"])
        area = w * h
        if area == 0:
            errors.append(self.create_error(annotation=annotation,
                                            error_code=f'bounds area 0',
                                            error_detail=f'points: {annotation["points"]}'))

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        self._validate_point_length(errors, annotation)
        self._validate_maximum_point_length(errors, annotation)
        self._validate_minimum_point_length(errors, annotation)
        self._validate_polygon_bounds_area(errors, annotation)

        return errors


class AnnotationKeypointValidator(AnnotationValidator):
    def __init__(self, length=None, max_length=None, start_key='0', is_warning=False):
        super().__init__(is_warning)
        self.length = length
        self.max_length = max_length
        self.start_key = start_key

    def is_checkable(self, annotation):
        return annotation["type"] == "keypoint"

    def _get_max_key(self, keypoints):
        keys = keypoints.keys()

        return str(max(int(key) for key in keys))

    def _validate_point_length(self, errors, annotation):
        if self.length is None:
            return

        if len(annotation["keypoints"]) != self.length:
            errors.append(self.create_error(annotation=annotation, error_code='length_error',
                                            error_detail=f'keypoints count : {len(annotation["keypoints"])}'))

    def _validate_max_length(self, errors, annotation):
        if self.max_length is None:
            return

        if len(annotation["keypoints"]) > self.max_length:
            errors.append(self.create_error(annotation=annotation, error_code='length_error',
                                            error_detail=f'keypoints count : {len(annotation["keypoints"])}'))

    def _validate_max_key(self, errors, annotation):
        if self.max_length is None and self.length is None:
            return

        expected_max_key = str(self.max_length or self.length + int(self.start_key))
        max_key = self._get_max_key(annotation["keypoints"])

        if int(max_key) > int(expected_max_key):
            errors.append(self.create_error(annotation=annotation, error_code='max_key_number_error',
                                            error_detail=f'max key : {max_key}'))

    def _validate_key_type(self, errors, annotation):
        for key in annotation["keypoints"].keys():
            if isinstance(key, str) == False:
                errors.append(
                    self.create_error(annotation=annotation, error_code='key_is_not_str', error_detail=f'{type(key)}'))
                break

        for key in annotation["invisible_keys"]:
            if isinstance(key, str) == False:
                errors.append(self.create_error(annotation=annotation, error_code='invisible_key_is_not_str',
                                                error_detail=f'{type(key)}'))
                break

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        self._validate_point_length(errors, annotation)
        self._validate_max_length(errors, annotation)
        self._validate_max_key(errors, annotation)
        self._validate_key_type(errors, annotation)

        return errors


class AnnotationCuboid3DValidator(AnnotationValidator):
    def __init__(self, check_point_count=False, is_warning=False):
        super().__init__(is_warning)
        self.check_point_count = check_point_count

    def is_checkable(self, annotation):
        return annotation['type'] == AnnotationType.cuboid.value

    def _validate_nonzero_geometry_values(self, errors, annotation):
        if not all(geometry := annotation["geometry"]):
            errors.append(
                self.create_error(annotation=annotation, error_code='zero_geometry_element_error', error_detail=f'geometry: {geometry}')
            )

    def _validate_range_of_rotation_values(self, errors, annotation):
        def _is_out_of_rotation_range(rotation_value):
            min_rotation_value, max_rotation_value = -0.5 * math.pi, 1.5 * math.pi
            return (rotation_value < min_rotation_value) or (rotation_value > max_rotation_value)

        rotation = annotation["rotation"]
        out_of_range_values = list(filter(_is_out_of_rotation_range, rotation))

        if out_of_range_values:
            errors.append(
                self.create_error(annotation=annotation, error_code='rotation_range_error',
                                  error_detail=f'rotation value is not in -0.5*pi <= rotation_xyz <= 1.5*pi\nrotation: {rotation}')
            )

    def _validate_point_count_existence(self, errors, annotation):
        if annotation.get("point_count") is None:
            errors.append(
                self.create_error(annotation=annotation, error_code='point_count_existence_error', error_detail='point_count_does_not_exist')
            )

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        self._validate_nonzero_geometry_values(errors, annotation)
        self._validate_range_of_rotation_values(errors, annotation)
        if self.check_point_count:
            self._validate_point_count_existence(errors, annotation)

        return errors


class AnnotationPolySegValidator(AnnotationPolygonValidator):
    def is_checkable(self, annotation):
        return annotation['type'] == 'poly_seg'


class AnnotationTypeValidator(AnnotationValidator):
    def __init__(self, possible_annotation_types, is_warning=False):
        super().__init__(is_warning)
        self.possible_annotation_types = set(possible_annotation_types)

    def is_checkable(self, annotation):
        return True

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []

        if annotation['type'] not in self.possible_annotation_types:
            errors.append(
                self.create_error(annotation=annotation, error_code='annotation_type_error',
                                  error_detail=f'wrong annotation type : {annotation["type"]}'))

        return errors


class AnnotationClassValidator(AnnotationValidator):
    def __init__(self, type_classes, is_warning=False):
        super().__init__(is_warning)
        self.type_classes = type_classes

    def is_checkable(self, annotation):
        return annotation['type'] in self.type_classes

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        possible_classes = self.type_classes[annotation['type']]

        errors = []
        if annotation['label'] not in possible_classes:
            error = self.create_error(annotation=annotation, error_code='class_error',
                                      error_detail=f'wrong annotation class : {annotation["label"]}')
            errors.append(error)

        return errors


class AnnotationAttributeKeyValidator(AnnotationValidator):
    def __init__(self, class_attribute_keys, is_warning=False):
        super().__init__(is_warning)
        self.class_attribute_keys = class_attribute_keys

    def is_checkable(self, annotation):
        return annotation['label'] in self.class_attribute_keys

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        attribute_keys = self.class_attribute_keys[annotation['label']]

        errors = []

        attributes = annotation['attributes']
        for attribute_key in attribute_keys:
            if attribute_key not in attributes:
                error = self.create_error(annotation=annotation, error_code='속성이 선택되지 않은 인스턴스가 존재합니다.',
                                          error_detail=f'<em>{attribute_key}</em> 속성을 선택해주세요.')
                errors.append(error)

        return errors


class AnnotationAttributeValueValidator(AnnotationValidator):
    """
    key_values : {key1: [value1, value2, ...], ...}
    key_values_by_classes: {class_name1: {key1: [value1, value2, ...], ...}, ...}
    """
    def __init__(self, key_values=None, key_values_by_classes=None, is_warning=False):
        super().__init__(is_warning)
        self.key_values = key_values
        self.key_values_by_classes = key_values_by_classes

    def is_checkable(self, annotation):
        _is_checkable = True
        if self.key_values_by_classes:
            _is_checkable = annotation['label'] in self.key_values_by_classes
        return _is_checkable

    def _validate_choice_type(self, attribute_key, attribute_value, available_values, annotation):
        if attribute_value not in available_values:
            track_id = annotation.get("track_id")
            if track_id:
                error_detail = f'{attribute_key}: {attribute_value}\ntrack_id: {track_id}'
            else:
                error_detail = f'{attribute_key} : {attribute_value}'

            return self.create_error(annotation=annotation, error_code='attribute_value_error',
                                     error_detail=error_detail)

    def _validate_multi_choice_type(self, attribute_key, attribute_values, available_values, annotation):
        errors = []
        for value in attribute_values:
            if value not in available_values:
                error = self.create_error(annotation=annotation, error_code='attribute_value_error',
                                          error_detail=f'{attribute_key} : {value}')
                errors.append(error)

        return errors

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []

        if self.key_values is None and self.key_values_by_classes is None:
            raise ValueError("key_values or key_values_by_classes must be set")

        for key, values in annotation['attributes'].items():
            available_values = None

            if self.key_values:
                available_values = self.key_values.get(key)
            elif self.key_values_by_classes:
                available_key_values_by_class = self.key_values_by_classes[annotation["label"]]
                available_values = available_key_values_by_class.get(key)

            if available_values is None:
                continue

            if isinstance(values, str):
                value_error = self._validate_choice_type(key, values, available_values, annotation)
                if value_error:
                    errors.append(value_error)

            elif isinstance(values, list):
                value_errors = self._validate_multi_choice_type(key, values, available_values, annotation)
                errors.extend(value_errors)

        return errors


class AnnotationMinSizeValidator(AnnotationValidator):
    def __init__(self, min_width=0, min_height=0, is_and_condition=True, is_warning=False):
        super().__init__(is_warning)
        self.min_width = min_width
        self.min_height = min_height
        self.is_and_condition = is_and_condition

    def is_checkable(self, annotation):
        annotation_type = annotation["type"]

        return annotation_type in [AnnotationType.bbox.value, AnnotationType.polygon.value, AnnotationType.poly_seg.value,
                                   AnnotationType.landmark.value, AnnotationType.obbox_v2.value]

    def _get_wh(self, annotation):
        annotation_type = annotation["type"]

        if annotation_type == AnnotationType.obbox_v2.value:
            _, _, w, h = annotation["rect"]

        else:
            if annotation_type == AnnotationType.landmark.value:
                points = list(annotation["keypoints"].values())
            else:
                points = annotation["points"]

            w, h = get_wh(points)

        return w, h

    def _validate_one_side(self, errors, annotation, side_to_check):
        width, height = self._get_wh(annotation)

        annotation_size = width if side_to_check == 'width' else height
        standard_size = self.min_width if side_to_check == 'width' else self.min_height

        if not (annotation_size >= standard_size):
            errors.append(self.create_error(annotation=annotation, error_code=f'annotations_{side_to_check}_error',
                                            error_detail=f'standard {side_to_check} : {standard_size} / \n'
                                                         f'annotation {side_to_check} : {annotation_size}'))

    def _validate_both_side(self, errors, annotation):
        width, height = self._get_wh(annotation)

        is_error = False
        if self.is_and_condition:
            if not (width >= self.min_width and height >= self.min_height):
                is_error = True

        else:
            if not (width >= self.min_width or height >= self.min_height):
                is_error = True

        if is_error:
            errors.append(self.create_error(annotation=annotation, error_code='annotations_size_error',
                                            error_detail=f'standard width, standard height : {self.min_width, self.min_height} / \n'
                                                         f'annotation width, annotation height : {width, height}'))

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []

        if self.min_width == 0 and self.min_height != 0:
            self._validate_one_side(errors, annotation, side_to_check='height')

        elif self.min_width != 0 and self.min_height == 0:
            self._validate_one_side(errors, annotation, side_to_check='width')

        elif self.min_width != 0 and self.min_height != 0:
            self._validate_both_side(errors, annotation)

        else:
            raise ValueError

        return errors


class AnnotationCuboidMinSizeValidator(AnnotationValidator):
    def __init__(self, min_length=0, min_width=0, min_height=0, is_warning=False):
        super().__init__(is_warning)
        self.min_geometry_list = [min_length, min_width, min_height]

    def is_checkable(self, annotation):
        annotation_type = annotation["type"]
        return annotation_type == AnnotationType.cuboid.value

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        instance_geometry = annotation["geometry"]
        length_width_height = ["length", "width", "height"]  # cuboid annotation의 geometry에 들어가는 순서

        for index, value in enumerate(length_width_height):
            if instance_geometry[index] < self.min_geometry_list[index]:
                errors.append(
                    self.create_error(annotation, f'cuboid_min_{value}_error',
                                      f'min_{value}: {self.min_geometry_list[index]}\n'
                                      f'labeled_instance_length: {instance_geometry[index]}')
                )
        return errors


class AnnotationDuplicatedPointValidator(AnnotationValidator):
    def __init__(self, check_nonserial_duplication=False, is_warning=False):
        super().__init__(is_warning)
        self.check_nonserial_duplication = check_nonserial_duplication

    def is_checkable(self, annotation):
        return annotation['type'] == 'polygon' or annotation['type'] == 'polyline'

    def _get_start_end_duplicated_point(self, annotation):
        if annotation['points'][0] == annotation['points'][-1]:
            return tuple(annotation['points'][0])
        return None

    def _validate_start_end_duplicated_point(self, errors, annotation, start_end_duplicated_point):
        if start_end_duplicated_point:
            errors.append(self.create_error(annotation=annotation, error_code='start_end_duplicated_point',
                                            error_detail=f"duplicated_point: {start_end_duplicated_point}"))

    def _get_serial_duplicated_points(self, annotation):
        points = annotation['points']
        points_length = len(points)
        serial_duplicated_points = []

        for i in range(points_length - 1):
            if points[i] == points[i + 1]:
                serial_duplicated_points.append(tuple(points[i]))
        return serial_duplicated_points

    def _validate_serial_duplicated_point(self, errors, annotation, serial_duplicated_points):
        if serial_duplicated_points:
            for point in serial_duplicated_points:
                errors.append(self.create_error(annotation=annotation, error_code='serial_duplicated_point',
                                                error_detail=f'duplicated_point: {point}'))

    def _validate_nonserial_duplicated_point(self, errors, annotation, start_end_duplicated_point,
                                             serial_duplicated_points):
        if not self.check_nonserial_duplication:
            return

        duplicated_points = list(tuple(point) for point in annotation['points'])
        duplicated_count = Counter(duplicated_points)

        for value, count in duplicated_count.items():
            if count >= 2:
                if (value != start_end_duplicated_point) and (value not in serial_duplicated_points):
                    errors.append(self.create_error(annotation=annotation, error_code='duplicated_point',
                                                    error_detail=f'duplicated_point: {value}, '
                                                                 f'duplication_count: {count}',
                                                    is_warning=True))

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        unique_points = set(tuple(point) for point in annotation['points'])

        if len(unique_points) != len(annotation['points']):
            start_end_duplicated_point = self._get_start_end_duplicated_point(annotation)
            serial_duplicated_points = self._get_serial_duplicated_points(annotation)

            self._validate_start_end_duplicated_point(errors, annotation, start_end_duplicated_point)
            self._validate_serial_duplicated_point(errors, annotation, serial_duplicated_points)
            self._validate_nonserial_duplicated_point(errors, annotation, start_end_duplicated_point,
                                                      serial_duplicated_points)

        return errors


class AnnotationClockwisePointValidator(AnnotationValidator):
    def is_checkable(self, annotation):
        return True

    def validate(self, annotation, metadata=None):
        errors = []
        points = annotation["points"]
        if not is_clockwise_order(points):
            errors.append(self.create_error(
                annotation, error_code='counter_clockwise_points',
                error_detail=f'labeled_points: {points}'
            ))
        return errors


class AnnotationPolygonAreaValidator(AnnotationValidator):
    def __init__(self, minimum_polygon_area, is_warning=False):
        super().__init__(is_warning)
        self.minimum_polygon_area = minimum_polygon_area

    def is_checkable(self, annotation):
        return annotation["type"] in [AnnotationType.polygon.value, AnnotationType.poly_seg.value]

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        points = annotation["points"]
        polygon_area = Polygon(points).buffer(0).area  # *self-intersection-polygon issue
        if polygon_area < self.minimum_polygon_area:
            errors.append(
                self.create_error(annotation, error_code="less_than_the_limit_of_minimum_polygon_area",
                                  error_detail=f"minimum_polygon_area: {self.minimum_polygon_area}\n"
                                               f"instsance_polygon_area: {polygon_area}",
                                  is_warning=self.is_warning)
            )
        return errors


class AnnotationCuboidMinPointCountValidator(AnnotationValidator):
    def __init__(self, min_point_count, is_warning=False):
        super().__init__(is_warning)
        self.min_point_count = min_point_count

    def is_checkable(self, annotation):
        return annotation.get("point_count")

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        point_count = annotation["point_count"]
        if point_count < self.min_point_count:
            errors.append(
                self.create_error(annotation,
                                  error_code="cuboid_min_point_count_error",
                                  error_detail=f"minimum_point_count: {self.min_point_count}\n"
                                               f"instsance_point_count: {point_count}",
                                  is_warning=self.is_warning)
            )
        return errors


class AnnotationTruncationValidator(AnnotationValidator):
    """
    Truncation 작업 진행시, Error여부 반환
    이미지 모서리쪽에 걸친 인스턴스는 Truncation이 0%이면 warning 처리
    인스턴스가 이미지 내부에 있는데 Truncation이 0%가 아닌 경우 error 처리

    truncation_key : str
        라벨러스 프로젝트 설정에서 PM이 지정한 Attributes Truncation Key값
    not_truncated_value : str
        라벨러스 프로젝트 설정에서 PM이 지정한 Attributes Truncation 에서 이미지 잘림이 없는 경우의 Value
    target_class: List
        라벨러스 truncation 검사 대상 class List(default=None, None일 경우 모든 인스턴스 검사)
    edge_instance_truncation_error: bool
        이미지 모서리쪽에 걸친 인스턴스는 Truncation이 0%이면 error 처리(default=False)
    inner_instance_truncation_error: bool
        인스턴스가 이미지 내부에 있는데 Truncation이 0%가 아닌 경우 error 처리(default=False)
    """

    def __init__(self, truncation_key="Truncation", no_truncation_value="0", target_classes: List = None,
                 edge_instance_truncation_warning=False, inner_instance_truncation_warning=False):
        super().__init__(is_warning=True)
        self.truncation_key = truncation_key
        self.no_truncation_value = no_truncation_value
        self.target_classes = target_classes
        self.edge_instance_truncation_warning = edge_instance_truncation_warning
        self.inner_instance_truncation_warning = inner_instance_truncation_warning

    def is_checkable(self, annotation):
        return annotation["attributes"].get(self.truncation_key)

    def get_target_annotations(self, annotations):
        if self.target_classes:
            target_annotations = [annotation for annotation in annotations if annotation["label"] in self.target_classes]
            return target_annotations
        return annotations

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        image_width, image_height = metadata["width"], metadata["height"]

        points = annotation["points"]
        if has_outside_point(image_width, image_height, points):
            points = outside_points_to_inside_points(image_width, image_height, points)

        x_coords, y_coords = zip(*points)
        truncation = annotation['attributes'].get(self.truncation_key)

        if truncation == self.no_truncation_value:
            if (image_width in x_coords) or (0 in x_coords) or (image_height in y_coords) or (0 in y_coords):
                errors.append(
                    self.create_error(
                        annotation=annotation, error_code=f'Truncation 오류',
                        error_detail=f'Truncation이 없는 경우 bbox가 이미지의 상하좌우 끝에 맞닿아 있으면 안됩니다.',
                        is_warning=self.edge_instance_truncation_warning)
                )

        else:
            if (image_width not in x_coords) and (0 not in x_coords) and (image_height not in y_coords) and (0 not in y_coords):
                errors.append(
                    self.create_error(
                        annotation=annotation, error_code=f'Truncation 오류',
                        error_detail='Truncation이 있는 경우 bbox가 이미지의 상하좌우 끝에 반드시 맞닿아야 합니다.',
                        is_warning=self.inner_instance_truncation_warning)
                )

        return errors


class AnnotationGroupIdValidator(AnnotationValidator):
    def is_checkable(self, annotation):
        return True

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        if annotation.get('group_id') is None:
            errors.append(self.create_error(
                annotation, f'no_group_id_error', f'group id should be labeled in {annotation["label"]}'
            ))
        return errors


class AnnotationMaxSizeValidator(AnnotationValidator):
    def __init__(self, max_width=None, max_height=None, is_and_condition=True, is_warning=False):
        super().__init__(is_warning)
        self.max_width = max_width
        self.max_height = max_height
        self.is_and_condition = is_and_condition

    def is_checkable(self, annotation):
        annotation_type = annotation["type"]

        return annotation_type in [AnnotationType.bbox.value, AnnotationType.polygon.value, AnnotationType.poly_seg.value,
                                   AnnotationType.landmark.value, AnnotationType.obbox_v2.value]

    def _get_wh(self, annotation):
        annotation_type = annotation["type"]

        if annotation_type == AnnotationType.obbox_v2.value:
            _, _, w, h = annotation["rect"]

        else:
            if annotation_type == AnnotationType.landmark.value:
                points = list(annotation["keypoints"].values())
            else:
                points = annotation["points"]

            w, h = get_wh(points)

        return w, h

    def _validate_one_side(self, errors, annotation, side_to_check):
        width, height = self._get_wh(annotation)

        annotation_size = width if side_to_check == 'width' else height
        standard_size = self.max_width if side_to_check == 'width' else self.max_height

        if not (annotation_size >= standard_size):
            errors.append(self.create_error(annotation=annotation, error_code=f'annotations_{side_to_check}_error',
                                            error_detail=f'max {side_to_check} : {standard_size} / \n'
                                                         f'annotation {side_to_check} : {annotation_size}'))

    def _validate_both_side(self, errors, annotation):
        width, height = self._get_wh(annotation)

        is_error = False
        if self.is_and_condition:
            if not (width <= self.max_width and height <= self.max_height):
                is_error = True

        else:
            if not (width <= self.max_width or height <= self.max_height):
                is_error = True

        if is_error:
            errors.append(self.create_error(annotation=annotation, error_code='annotations_size_error',
                                            error_detail=f'max width, max height : {self.max_width, self.max_height} / \n'
                                                         f'annotation width, annotation height : {width, height}'))

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []

        if not self.max_width and self.max_height:
            self._validate_one_side(errors, annotation, side_to_check='height')

        elif self.max_width and not self.max_height:
            self._validate_one_side(errors, annotation, side_to_check='width')

        elif self.max_width and self.max_height:
            self._validate_both_side(errors, annotation)

        else:
            raise ValueError

        return errors
