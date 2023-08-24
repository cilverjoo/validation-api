import copy
from typing import List, Tuple

from funcy import cached_property

from app.models.validation import AnnotationError, GtError
from app.validations.utils.config import AnnotationType


class AnnotationValidator:
    def __init__(self, is_warning=False):
        self.is_warning = is_warning

    def create_error(self, annotation, error_code, error_detail, is_warning=None):
        if is_warning is None:
            is_warning = self.is_warning
        return AnnotationError(annotationId=annotation['id'], annotationType=annotation['type'],
                               message=error_detail, description=error_code, richMessage=error_code,
                               is_warning=is_warning)

    def is_checkable(self, annotation):
        raise NotImplementedError

    def validate(self, annotation, metadata=None) -> List[AnnotationError]:
        return []


class GtValidator:
    def __init__(self, is_warning=False):
        self.is_warning = is_warning

    def create_error(self, error_code, error_detail, is_warning=None):
        if is_warning is None:
            is_warning = self.is_warning
        return GtError(message=error_detail, richMessage=error_code, is_warning=is_warning)

    def validate(self, gt) -> List[GtError]:
        return []


class Validator:
    def __init__(self):
        self.annotation_validators = []
        self.gt_validators = []

    def add_annotation_validators(self, annotation_validators):
        self.annotation_validators.extend(annotation_validators)

    def add_gt_validators(self, gt_validators):
        self.gt_validators.extend(gt_validators)

    def validate(self, gt) -> Tuple[List[GtError], List[AnnotationError]]:
        gt_errors = []
        annotation_errors = []

        for gt_validator in self.gt_validators:
            gt_errors.extend(gt_validator.validate(gt))

        for annotation in gt['annotations']:
            for annotation_validator in self.annotation_validators:
                if not annotation_validator.is_checkable(annotation):
                    continue

                annotation_errors.extend(annotation_validator.validate(annotation, gt.get('metadata')))

        return gt_errors, annotation_errors


class ValidationProcess:
    @property
    def annotation_validators(self):
        return []

    @property
    def gt_validators(self):
        return []

    @cached_property
    def validator(self):
        validator = Validator()
        validator.add_annotation_validators(self.annotation_validators)
        validator.add_gt_validators(self.gt_validators)
        return validator

    def studio_gt_to_output_gt(self, studio_gt):
        annotations = []
        for studio_annotation in studio_gt["annotations"]:
            annotation = copy.deepcopy(studio_annotation)

            group_id = annotation.pop("groupId")
            if group_id is not None:
                annotation["group_id"] = group_id

            track_id = annotation.pop("trackId")
            if track_id is not None:
                annotation["track_id"] = track_id

            label = annotation["attributes"].pop("cla$$")
            annotation["label"] = label

            annotation['type'] = AnnotationType[annotation['type']].value
            if annotation["type"] == AnnotationType.landmark.value:
                invisible_keys = annotation.pop("invisibleKeys")
                annotation["invisible_keys"] = invisible_keys

            annotations.append(annotation)

        studio_gt["annotations"] = annotations
        return studio_gt

    def validate_gt(self, gt) -> Tuple[List[GtError], List[AnnotationError]]:
        if 'annotations' not in gt:
            return [], []

        gt_errors, annotation_errors = self.validator.validate(self.studio_gt_to_output_gt(gt))
        return gt_errors, annotation_errors
