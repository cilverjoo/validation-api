from typing import List

from funcy import group_by

from app.models.validation import AnnotationError, GtError
from app.validations.modules import AnnotationValidator, GtValidator
from app.validations.utils.shape import get_bounds, get_iou


class GtODTireLicensePlateGroupValidator(GtValidator):
    def _is_out_of_car(self, car_points, points):
        c_min_x, c_min_y, c_max_x, c_max_y = sum(get_bounds(car_points), ())
        lt_min_x, lt_min_y, lt_max_x, lt_max_y = sum(get_bounds(points), ())

        return (lt_min_x < c_min_x) or (lt_min_y < c_min_y) or (c_max_x < lt_max_x) or (c_max_y < lt_max_y)

    @property
    def tire_license_plate_classes(self):
        return ["wheel_ignored", "wheel", "wheel_2pt", "licenseplate"]

    def validate_annotation_without_group(self, annotation, errors):
        if annotation['label'] in self.tire_license_plate_classes:
            errors.append(
                self.create_error(
                    error_code=f'그룹이 지정되지 않은 인스턴스가 존재합니다 : <em>{annotation["label"]}(ID: {annotation["id"].split("-")[0]})</em>',
                    error_detail=f'{annotation["label"]}의 그룹이 지정되지 않았습니다.'))

    def validate_group_length(self, group_annotations, tool_group_id, errors):
        if len(group_annotations) == 1:
            errors.append(self.create_error(error_code=f'<em>{tool_group_id}</em>: 1개의 인스턴스만 포함하고 있습니다.',
                                            error_detail='1개의 인스턴스만 그룹화 될 수 없습니다.'))

    def validate_group_without_car(self, tool_group_id, errors):
        errors.append(self.create_error(error_code=f'<em>{tool_group_id}</em>: 차량 클래스가 없는 그룹은 있을 수 없습니다.',
                                        error_detail='차량 클래스가 없는 그룹은 있을 수 없습니다.'))

    def validate_group_with_car(self, tool_group_id, errors):
        errors.append(self.create_error(error_code=f'<em>{tool_group_id}</em>: 한 그룹 내에 두 개 이상의 차량 클래스가 존재할 수 없습니다.',
                                        error_detail='한 그룹 내에 두 개 이상의 차량 클래스가 존재할 수 없습니다.'))

    def validate_group_with_tire_license_plate(self, tire_license_plate_annotation, car_annotation, tool_group_id, errors):
        iou = get_iou(car_annotation['points'], tire_license_plate_annotation['points'])
        if iou == 0.0:
            errors.append(self.create_error(
                error_code=f'<em>{tool_group_id}</em>: 그룹 범위를 벗어난 <em>{tire_license_plate_annotation["label"]}</em> 이(가) 존재합니다.',
                error_detail=f'{tire_license_plate_annotation["label"]}은 그룹 범위를 벗어날 수 없습니다.'))

    def count_licenseplate_annotations(self, annotations):
        # 그룹내에 licenseplate가 있으면 +1, 여러개여도 1개로 카운트
        return 1 if any(annotation.get('label') == 'licenseplate' for annotation in annotations) else 0

    def validate_group_with_licenseplate_3more(self, have_group_id_licenseplate, errors):
        errors.append(self.create_error(
            error_code=f'<em>번호판은 최대 3대의 차량</em>만 작업 대상입니다.',
            error_detail=f'번호판은 최대 3대의 차량만 작업 대상입니다. 그룹id를 가진 licenseplate 개수 : {have_group_id_licenseplate}'))

    def validate(self, gt) -> List[GtError]:
        errors = []
        annotations_with_group = []
        have_group_id_licenseplate = 0

        for annotation in gt['annotations']:
            if annotation.get('group_id'):
                annotations_with_group.append(annotation)
            else:
                self.validate_annotation_without_group(annotation, errors)

        annotation_groups = group_by(lambda annotation: annotation['group_id'], annotations_with_group)

        for group_id, group_annotations in annotation_groups.items():
            tool_group_id = f'G{group_id.split("-")[0]}'
            self.validate_group_length(group_annotations, tool_group_id, errors)

            tire_license_plate_annotations = [annotation for annotation in group_annotations
                                              if annotation['label'] in self.tire_license_plate_classes]
            car_annotation = [annotation for annotation in group_annotations
                               if annotation['label'] not in self.tire_license_plate_classes]

            # 그룹내에 차량이 포함되지 않은경우
            if not car_annotation:
                self.validate_group_without_car(tool_group_id, errors)
            # 그룹 내 차량이 1개가 아닌 경우
            elif len(car_annotation) > 1:
                self.validate_group_with_car(tool_group_id, errors)
            else:
                for tire_license_plate_annotation in tire_license_plate_annotations:
                    # 그룹 내에 차량이 포함된 경우, 타이어/번호판 위치 확인
                    self.validate_group_with_tire_license_plate(
                        tire_license_plate_annotation, car_annotation[0], tool_group_id, errors)

            licenseplate_count = self.count_licenseplate_annotations(group_annotations)
            have_group_id_licenseplate += licenseplate_count

        if have_group_id_licenseplate > 3:
            self.validate_group_with_licenseplate_3more(have_group_id_licenseplate, errors)

        return errors


class AnnotationLicenseplateHeightValidator(AnnotationValidator):
    def is_checkable(self, annotation):
        return annotation['label'] == 'licenseplate'

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        errors = []
        _, min_y, _, max_y = sum(get_bounds(annotation['points']), ())
        licenseplate_height = max_y - min_y
        if licenseplate_height < 8:
            error = self.create_error(annotation=annotation, error_code='<em>번호판의 높이가 8px 미만일 수 없습니다.</em>',
                                      error_detail=f'번호판의 높이가 8px 미만일 수 없습니다. 현재 : {licenseplate_height}')
            errors.append(error)

        return errors
