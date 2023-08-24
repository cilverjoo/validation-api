from app.validations.modules import ValidationProcess
from app.validations.modules.annotation import AnnotationBboxValidator
from app.validations.modules.gt import GtEmptyValidator, GtIoUValidator
from app.validations.projects.year_2023.sample.od_tire_licenseplate.v1.validator import AnnotationLicenseplateHeightValidator, \
    GtStradvisionODTireLicensePlateGroupValidator


class GtValidationProcess(ValidationProcess):
    @property
    def annotation_validators(self):
        return [
            AnnotationBboxValidator(),
            AnnotationLicenseplateHeightValidator()
        ]

    @property
    def gt_validators(self):
        return {
            GtEmptyValidator(is_warning=True),
            GtIoUValidator(threshold_iou=0.9, is_warning=True),
            GtStradvisionODTireLicensePlateGroupValidator()
        }
