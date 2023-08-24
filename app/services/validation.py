import importlib

from app.models.validation import ValidationModel, GtErrorResponse, AnnotationErrorResponse


def validate_by_url(gt, parsed_url):

    project = parsed_url.project.replace('-', '_')
    import_path = f'app.validations.projects.year_{parsed_url.year}.{parsed_url.customer}.{project}.v{parsed_url.version}'
    validation_module = importlib.import_module(import_path)

    gt_errors, annotation_errors = validation_module.GtValidationProcess().validate_gt(gt)

    if gt_errors or annotation_errors:
        return ValidationModel(
            success=False,
            globalErrors=GtErrorResponse(
                warnings=[gt_error for gt_error in gt_errors if gt_error.is_warning is True],
                errors=[gt_error for gt_error in gt_errors if gt_error.is_warning is False]
            ),
            annotationErrors=AnnotationErrorResponse(
                warnings=[annotation_error for annotation_error in annotation_errors if annotation_error.is_warning is True],
                errors=[annotation_error for annotation_error in annotation_errors if annotation_error.is_warning is False]
            )
        )
    return ValidationModel(success=True)


def validate_by_common_gt_validator(validator, gt):
    gt_errors = validator.validate(gt)
    return gt_error_to_model(gt_errors)


def validate_by_common_annotation_validator(validator, gt):
    annotation_errors = []
    for annotation in gt['annotations']:
        annotation_error = validator.validate(annotation)
        annotation_errors.append(annotation_error)
    return annotation_error_to_model(annotation_errors)


def gt_error_to_model(gt_errors):
    if gt_errors:
        return ValidationModel(
            success=False,
            globalErrors=GtErrorResponse(
                warnings=[gt_error for gt_error in gt_errors if gt_error.is_warning is True],
                errors=[gt_error for gt_error in gt_errors if gt_error.is_warning is False]
            )
        )
    return ValidationModel(success=True)


def annotation_error_to_model(annotation_errors):
    if annotation_errors:
        return ValidationModel(
            success=False,
            annotationErrors=GtErrorResponse(
                warnings=[annotation_error for annotation_error in annotation_errors if annotation_error.is_warning is True],
                errors=[annotation_error for annotation_error in annotation_errors if annotation_error.is_warning is False]
            )
        )
    return ValidationModel(success=True)
