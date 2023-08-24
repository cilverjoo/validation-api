from enum import Enum


class AttributeConfigType(Enum):
    choice = 'choice'
    multi_choice = 'multi_choice'


class AnnotationType(Enum):
    polygon = 'polygon'
    poly_seg = 'poly_seg'
    bbox = 'bbox'
    cuboid = 'cuboid'
    obbox_v2 = 'obbox_v2'
    cuboid_plain = 'flat_cuboid'
    landmark = 'keypoint'
    polyline = 'polyline'

