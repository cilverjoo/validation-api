import copy
import json
from collections import Counter
from typing import List

from app.models.validation import GtError
from app.validations.utils.config import AnnotationType, AttributeConfigType
from app.validations.utils.rgb import generate_rgb_tuples
from app.validations.utils.shape import get_iou, has_outside_point, get_rotated_4points_of_obbox_v2
from app.validations.modules import GtValidator


class GtEmptyValidator(GtValidator):
    def validate(self, gt) -> List[GtError]:
        errors = []
        annotations = gt['annotations']
        if not annotations:
            errors.append(self.create_error(
                error_code='라벨링된 인스턴스가 존재하지 않습니다.',
                error_detail=f'라벨링된 인스턴스 갯수 : {len(annotations)}'))

        return errors


class GtLengthValidator(GtValidator):
    def __init__(self, length, is_warning=False):
        super().__init__(is_warning)
        self.length = length

    def validate(self, gt):
        errors = []

        if len(gt['annotations']) != self.length:
            errors.append(self.create_error('annotation_length_error', f'annotation count : {len(gt["annotations"])}'))

        return errors


class GtMinLengthValidator(GtValidator):
    def __init__(self, length, is_warning=False):
        super().__init__(is_warning)
        self.length = length

    def validate(self, gt):
        errors = []

        if len(gt['annotations']) < self.length:
            errors.append(
                self.create_error('annotation_min_length_error', f'annotation count : {len(gt["annotations"])}'))

        return errors


class GtMaxLengthValidator(GtValidator):
    def __init__(self, length, is_warning=False):
        super().__init__(is_warning)
        self.length = length

    def validate(self, gt):
        errors = []

        if len(gt['annotations']) > self.length:
            errors.append(
                self.create_error('annotation_max_length_error', f'annotation count : {len(gt["annotations"])}'))

        return errors


class GtMetadataValidator(GtValidator):
    def validate(self, gt):
        errors = []

        metadata = gt.get("metadata")

        if not metadata:
            errors.append(
                self.create_error('metadata_error', f'gt has no metadata, check gt'))
        else:
            width, height = metadata.get("width"), metadata.get("height")
            if None in [width, height]:
                errors.append(
                    self.create_error('metadata_wh_error', f'width: {width}, height: {height}'))

        return errors


class GtPolySegVeiledInstanceValidator(GtValidator):
    def _get_color_points_pairs(self, colors, annotations):
        return [(colors[index], [tuple(point) for point in annotation['points']])
                for index, annotation in enumerate(annotations)]

    def validate(self, gt) -> List[GtError]:
        errors = []
        width = gt["metadata"].get("width")
        height = gt["metadata"].get("height")
        if (width is None) or (height is None):
            errors.append(self.create_error(
                error_code="메타 데이터 에러: 이미지의 너비/높이 정보가 제대로 전달되지 않았습니다. 이미지를 확인해 주세요.",
                error_detail="metadata 필드 또는 width, height 값이 존재하지 않습니다.")
            )
            return errors

        annotations = gt["annotations"]

        colors = generate_rgb_tuples(len(annotations))
        color_points_pairs = self._get_color_points_pairs(colors, annotations)

        from app.validations.utils.image import generate_masked_image

        masked_image_array = generate_masked_image(width, height, color_points_pairs)
        visible_colors_count = dict(masked_image_array.getcolors()) # count: color 구조
        visible_colors_count = {v: k for k, v in visible_colors_count.items()} # color: count 구조

        for index, color in enumerate(colors):
            target_annotation = annotations[index]
            if color not in visible_colors_count.keys():
                errors.append(self.create_error(
                    error_code=f'가려진 인스턴스가 존재합니다. 인스턴스 ID : <em>{target_annotation["id"].split("-")[0]}</em>',
                    error_detail=f'해당 인스턴스가 마스크 이미지 상에서 존재하지 않습니다.'
                ))
            else:
                # color는 존재하나, color 픽셀 개수가 3개, 5개, 10개가 안되는 경우
                if visible_colors_count[color] < 5:
                    errors.append(self.create_error(
                        error_code=f'거의 가려진 인스턴스가 존재합니다. 인스턴스 ID : <em>{target_annotation["id"].split("-")[0]}</em>',
                        error_detail=f'해당 인스턴스가 마스크 이미지 상에서 5개 미만의 픽셀만 존재합니다.',
                        is_warning=True
                    ))
                elif visible_colors_count[color] < 10:
                    errors.append(self.create_error(
                        error_code=f'거의 가려진 인스턴스가 존재합니다. 인스턴스 ID : <em>{target_annotation["id"].split("-")[0]}</em>',
                        error_detail=f'해당 인스턴스가 마스크 이미지에서 10개 미만의 픽셀만 존재합니다.',
                        is_warning=True
                    ))
        return errors


class GtSegmentationHollowPointValidator(GtValidator):
    def __init__(self, color_map, base_color=(50, 50, 50, 255), is_warning=False):
        super().__init__(is_warning)
        self.color_map = color_map
        self.available_colors = list(self.color_map.values())
        self.base_color = base_color

    def validate(self, gt) -> List[GtError]:
        errors = []
        width = gt["metadata"].get("width")
        height = gt["metadata"].get("height")
        if (width is None) or (height is None):
            errors.append(
                self.create_error(
                    error_code="메타데이터 에러 : 이미지의 너비/높이 정보가 제대로 전달되지 않았습니다. 다시 시도해주세요.",
                    error_detail="metadata 필드 또는 width, height 값이 존재하지 않습니다."
                )
            )
        else:
            from app.validations.utils.image import get_masked_image_from_gt
            masked_image = get_masked_image_from_gt(
                width=width, height=height, annotations=gt['annotations'], color_map=self.color_map
            )

            from app.validations.utils.image import has_hollow_point

            if has_hollow_point(image=masked_image, available_colors=self.available_colors, base_color=self.base_color):
                errors.append(self.create_error(
                    error_code='마스킹 영역 사이 빈점이 존재합니다.',
                    error_detail=f'GT로 생성한 마스크 이미지에 빈점이 존재합니다.'
                ))
        return errors


class GtIoUValidator(GtValidator):
    def __init__(self, threshold_iou, is_warning=False):
        super().__init__(is_warning)
        self.threshold_iou = threshold_iou

    def get_target_annotations(self, origin_annotations):
        target_annotation_types = [AnnotationType.poly_seg.value, AnnotationType.polygon.value, AnnotationType.bbox.value]
        return [annotation for annotation in origin_annotations if annotation["type"] in target_annotation_types]

    def validate(self, gt):
        errors = []

        origin_annotations = gt['annotations']
        target_annotations = self.get_target_annotations(origin_annotations)

        annotations = copy.deepcopy(target_annotations)
        while annotations:
            annotation = annotations.pop()
            annotation_points = annotation['points']

            for comparison_annotation in annotations:
                comparison_annotation_points = comparison_annotation['points']
                iou = get_iou(annotation_points, comparison_annotation_points)

                if self.threshold_iou == 0:
                    if iou > self.threshold_iou:
                        errors.append(
                            self.create_error(error_code=f'인스턴스 간 겹침이 존재. ID : <em>{annotation["id"].split("-")[0]}/'
                                              f'{comparison_annotation["id"].split("-")[0]}</em>',
                                              error_detail=f'인스턴스 간 겹침이 허용되는 비율({iou}) 이상입니다.'))
                else:
                    if iou >= self.threshold_iou:
                        errors.append(
                            self.create_error(error_code=f'인스턴스 간 겹침 존재. ID : <em>{annotation["id"].split("-")[0]}/'
                                              f'{comparison_annotation["id"].split("-")[0]}</em>',
                                              error_detail=f'인스턴스 간 겹침이 허용되는 비율({iou}) 이상입니다.'))

        return errors


class GtClassificationClassValidator(GtValidator):
    def __init__(self, classification_classes, is_warning=False):
        super().__init__(is_warning)
        self.classification_classes = classification_classes

    def validate(self, gt) -> List[GtError]:
        possible_classes = self.classification_classes
        errors = []
        gt_label = gt.get('label')
        #  classification의 경우 dictionary에 "label" key가 아예 존재하지 않는 경우가 있음
        #  issue-report 채널에 올려야할것 같기도합니다.
        if gt_label not in possible_classes:
            error = self.create_error(error_code='gt_class_error',
                                      error_detail=f'wrong annotation class : {gt_label}')
            errors.append(error)
        return errors


class GtAttributeKeyValidator(GtValidator):
    def __init__(self, attributes_keys, is_warning=False):
        super().__init__(is_warning)
        self.attributes_keys = attributes_keys

    def validate(self, gt) -> List[GtError]:
        errors = []
        if not gt.get('label') in self.attributes_keys:
            # is_checkable이 GtValidator에는 없음
            return errors
        attribute_keys = self.attributes_keys[gt.get('label')]
        attributes = gt['attributes']
        for attribute_key in attribute_keys:
            if attribute_key not in attributes:
                error = self.create_error(
                    error_code='gt_attribute_key_error',
                    error_detail=f'file does not have {attribute_key}',
                    is_warning=self.is_warning
                )
                errors.append(error)

        return errors


class GtAttributeValueValidator(GtValidator):
    def __init__(self, key_values, attribute_config_type=AttributeConfigType.choice.value, is_warning=False):
        super().__init__(is_warning)
        self.key_values = key_values
        self.attribute_config_type = attribute_config_type

    def _validate_choice_type(self, errors, attributes):
        for key, value in attributes.items():
            possible_values = self.key_values.get(key)

            if possible_values is None:
                continue

            if type(value) == list:
                error = self.create_error(error_code='attribute_value_type_error',
                                          error_detail=f'{key} requires only one choice - got: {value}')
                errors.append(error)

            if value not in possible_values:
                error = self.create_error(error_code='gt_attribute_value_error',
                                          error_detail=f'{key} : {value}',
                                          is_warning=self.is_warning)
                errors.append(error)

    def _validate_multi_choice_type(self, errors, attributes):
        for key, values in attributes.items():
            possible_values = self.key_values.get(key)

            if possible_values is None:
                continue

            if type(values) == str:
                error = self.create_error(error_code='attribute_value_type_error',
                                          error_detail=f'{key} requires multi choice - got: {values}')
                errors.append(error)

            for value in values:
                if value not in possible_values:
                    error = self.create_error(error_code='attribute_value_error',
                                              error_detail=f'{key} : {value}')
                    errors.append(error)

    def validate(self, gt) -> List[GtError]:
        errors = []

        attributes = gt["attributes"]
        if self.attribute_config_type == AttributeConfigType.choice.value:
            self._validate_choice_type(errors, attributes)

        elif self.attribute_config_type == AttributeConfigType.multi_choice.value:
            self._validate_multi_choice_type(errors, attributes)

        return errors


class GtTrackIdValidator(GtValidator):
    def _validate_track_id_existence(self, errors, annotations):
        for annotation in annotations:
            if annotation.get("track_id") is None:
                errors.append(self.create_error(error_code='track_id_is_not_existed',
                                                error_detail=f'annotation_id: {annotation["id"]}'))

    def _validate_duplicated_track_id(self, errors, annotations):
        track_ids = [annotation["track_id"] for annotation in annotations if annotation.get("track_id")]

        counter = Counter(track_ids)

        for track_id, count in counter.items():
            if count != 1:
                errors.append(self.create_error(error_code='duplicated_track_id',
                                                error_detail=f'track id {track_id} is duplicated. count : {count}'))

    def validate(self, gt) -> List[GtError]:
        errors = []

        annotations = gt['annotations']
        self._validate_track_id_existence(errors, annotations)
        self._validate_duplicated_track_id(errors, annotations)

        return errors


class GtOBBoxV2IOUValidator(GtValidator):
    """
    IOU가 threshold_iou 이상인 instance가 존재하는지 확인하는 validator
    :param threshold_iou: IOU threshold
    :param instance_count_to_check: instance_count_to_check만큼 instance를 확인하며, -1 인 경우 모든 instance를 확인
    """

    def __init__(self, threshold_iou, instance_count_to_check: int = 10, is_warning=False):
        super().__init__(is_warning)
        self.threshold_iou = threshold_iou
        self.instance_count_to_check = instance_count_to_check
        self._check_instance_count_to_check()

    def _check_instance_count_to_check(self):
        if self.instance_count_to_check != -1:
            if self.instance_count_to_check <= 0:
                raise ValueError("instance_count_to_check must be -1(meaning all) or positive integer")

    def is_duplicated_error(self, errors, instance_id, comparison_instance_id):
        error_instance_id_tuples = [(error.error_detail.split(', ')[0][16:], error.error_detail.split(', ')[1][27:])
                                    for error in errors]

        if ((instance_id, comparison_instance_id) in error_instance_id_tuples
                or (comparison_instance_id, instance_id) in error_instance_id_tuples):
            return True
        return False

    def validate_IOU_with_close_instance_by_axis(self, annotations, errors):
        while annotations:
            annotation = annotations.pop()
            rotated_4points = get_rotated_4points_of_obbox_v2(xywh=annotation['rect'], degree=annotation['degree'])
            comparison_annotations = annotations[
                                     -self.instance_count_to_check:]  # 끝에서 10개의 인스턴스. 남은 갯수가 10개 미만이면 나머지.

            for comparison_annotation in comparison_annotations:
                comparison_xywh = comparison_annotation['rect']
                comparison_degree = comparison_annotation['degree']
                comparison_annotation_points = get_rotated_4points_of_obbox_v2(xywh=comparison_xywh,
                                                                               degree=comparison_degree)
                iou = get_iou(rotated_4points, comparison_annotation_points)

                if self.threshold_iou == 0:
                    if (iou > self.threshold_iou) and not self.is_duplicated_error(errors, annotation['id'],
                                                                                   comparison_annotation['id']):
                        errors.append(
                            self.create_error('annotation_iou_error',
                                              f'annotation_id : {annotation["id"]}, '
                                              f'overlapped_annotation_id : {comparison_annotation["id"]}, '
                                              f'iou : {iou}'))

                else:
                    if (iou >= self.threshold_iou) and not self.is_duplicated_error(errors, annotation['id'],
                                                                                    comparison_annotation['id']):
                        errors.append(
                            self.create_error('annotation_iou_error',
                                              f'annotation_id : {annotation["id"]}, '
                                              f'overlapped_annotation_id : {comparison_annotation["id"]}, '
                                              f'iou : {iou}'))

    def get_unique_annotations(self, annotations):
        _annotation_ids = []
        unique_annotations = []
        for annotation in annotations:
            if annotation['id'] not in _annotation_ids:
                _annotation_ids.append(annotation['id'])
                unique_annotations.append(annotation)
        return unique_annotations

    def get_target_annotations(self, origin_annotations):
        return [annotation for annotation in origin_annotations if annotation['type'] == AnnotationType.obbox_v2.value]

    def validate(self, gt, physical_filename=None):
        errors = []

        target_annotations = self.get_target_annotations(gt['annotations'])
        if self.instance_count_to_check == -1:
            # meaning "all", comparison_annotations = annotations[-0:]
            self.instance_count_to_check = 0
            unique_annotations = target_annotations
        else:
            self.instance_count_to_check = int(self.instance_count_to_check)
            x_axis_sorted_annotations = sorted(target_annotations,
                                               key=lambda annotation: (annotation['rect'][0], annotation['rect'][1]))
            selected_x_annotations = x_axis_sorted_annotations[-self.instance_count_to_check:]
            y_axis_sorted_annotations = sorted(target_annotations,
                                               key=lambda annotation: (annotation['rect'][1], annotation['rect'][0]))

            selected_y_annotations = y_axis_sorted_annotations[-self.instance_count_to_check:]
            unique_annotations = self.get_unique_annotations([*selected_x_annotations, *selected_y_annotations])

        self.validate_IOU_with_close_instance_by_axis(unique_annotations, errors)
        return errors



class GtOutsidePointsValidator(GtValidator):
    def __init__(self, fixed_width=None, fixed_height=None, is_warning=False):
        super().__init__(is_warning)
        self.width = fixed_width
        self.height = fixed_height

    def _get_width_height(self, metadata):
        if self.width and self.height:
            width, height = self.width, self.height
        else:
            width, height = metadata.get("width"), metadata.get("height")
        return width, height

    def validate(self, gt) -> List[GtError]:
        errors = []
        image_width, image_height = self._get_width_height(gt["metadata"])

        for annotation in gt["annotations"]:
            if has_outside_point(image_width, image_height, annotation["points"]):
                _id, label = annotation["id"], annotation["label"]
                errors.append(
                    self.create_error("outside_points_error", f'outside points exists with annotation\n'
                                                              f'id:{_id}-label:{label}')
                )
        return errors
