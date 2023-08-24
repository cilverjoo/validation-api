import math

import numpy as np
from typing import List, Tuple
from shapely.geometry import Point, MultiPoint, Polygon


def flatten_points(points):
    return np.array(points).flatten().tolist()


def get_int_center_point(points):
    center_x, center_y = get_center_point(points)

    return int(center_x), int(center_y)


def get_bounds(points):
    x_coordinates, y_coordinates = zip(*points)
    return [(min(x_coordinates), min(y_coordinates)), (max(x_coordinates), max(y_coordinates))]


def get_center_point(points):
    left_top, right_bottom = get_bounds(points)

    return (left_top[0] + right_bottom[0]) / 2, (left_top[1] + right_bottom[1]) / 2


def get_bbox_center_bottom_point(points):
    left_top, right_bottom = get_bounds(points)

    return (left_top[0] + right_bottom[0]) / 2, right_bottom[1]


def get_wh(points):
    x_coordinates, y_coordinates = zip(*points)
    return (max(x_coordinates) - min(x_coordinates)), (max(y_coordinates) - min(y_coordinates))


def get_area(points):
    w, h = get_wh(points)
    return w * h


def get_xywh(points):
    x_coordinates, y_coordinates = zip(*points)

    return [min(x_coordinates),
            min(y_coordinates),
            max(x_coordinates) - min(x_coordinates),
            max(y_coordinates) - min(y_coordinates)]


def bounds_to_4points(bounds):
    left_top_point, right_bottom_point = bounds

    return [left_top_point,
            (right_bottom_point[0], left_top_point[1]),
            right_bottom_point,
            (left_top_point[0], right_bottom_point[1])]


def bounds_to_xywh(bounds):
    left_top_point, right_bottom_point = bounds
    return [left_top_point[0],
            left_top_point[1],
            abs(right_bottom_point[0] - left_top_point[0]),
            abs(right_bottom_point[1] - left_top_point[1])]


def xywh_to_bounds(xywh):
    x, y, w, h = xywh

    return [
        (x, y),
        (x + w, y + h)
    ]


def xywh_to_4points(xywh):
    x, y, w, h = xywh

    return [
        (x, y),
        (x + w, y),
        (x + w, y + h),
        (x, y + h)
    ]


def is_clockwise_order(points):
    area = 0
    for point, next_point in zip(points, list(points)[1:] + [points[0]]):
        current_x, current_y = point
        next_x, next_y = next_point
        area += current_x * next_y
        area -= next_x * current_y
    return area / 2 > 0


# 점이 반시계방향이면 시계방향으로 점 회전 - 첫 점 기준 (Flynn 제공)
def counterclockwise_to_clockwise(points):
    rounded_points = []
    for x_coordinate, y_coordinate in points:
        rounded_points.append([round(x_coordinate), round(y_coordinate)])

    if not is_clockwise_order(rounded_points):
        print('CONVERT TO CLOCKWISE')
        rounded_points = [points[0]] + list(reversed(points[1:]))

    return rounded_points


def get_iou(polygon1_points, polygon2_points):
    polygon1 = Polygon(polygon1_points)
    polygon2 = Polygon(polygon2_points)

    return polygon1.intersection(polygon2).area / polygon1.union(polygon2).area


def get_intersection_ratio_of_base_area(base_instance_points, comparison_instance_points):
    polygon1 = Polygon(base_instance_points)
    polygon2 = Polygon(comparison_instance_points)

    return polygon1.intersection(polygon2).area / polygon1.area


def get_obbox_degree(points, radian=False):
    """
    return degree or radian (float, -180 < degree ≤ 180 )
    """
    p1, p2, p3 = map(Point, points[:3])

    # get angle of upper corner(left-top point to right-top point)
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    _radian = math.atan2(dy, dx)

    if radian:
        return _radian
    return np.rad2deg(_radian)


def get_obbox_wh(points):
    p1, p2, p3 = map(Point, points[:3])
    width, height = p1.distance(p2), p2.distance(p3)

    return width, height


def points_to_rotated_4points(points, degree) -> List[Tuple]:
    from shapely.affinity import rotate
    return [(point.x, point.y) for point in rotate(MultiPoint(points), degree)]


def get_rotated_4points_of_obbox_v2(xywh, degree) -> List[Tuple]:
    original_points = xywh_to_4points(xywh)
    rotated_points = points_to_rotated_4points(original_points, degree)
    return rotated_points


def is_outside_point(image_width, image_height, point):
    x, y = point
    if (x < 0) or (x > image_width) or (y < 0) or (y > image_height):
        _is_outside_point = True
    else:
        _is_outside_point = False
    return _is_outside_point


def has_outside_point(image_width, image_height, points):
    _has_outside_points = False
    for point in points:
        if is_outside_point(image_width, image_height, point):
            _has_outside_points = True
            break
    return _has_outside_points


def outside_point_to_inside_point(image_width, image_height, point):
    x, y = point
    inside_x = 0 if x < 0 else image_width if x > image_width else x
    inside_y = 0 if y < 0 else image_height if y > image_height else y
    return [inside_x, inside_y]


def outside_points_to_inside_points(image_width, image_height, points):
    inside_points = []
    for point in points:
        if is_outside_point(image_width, image_height, point):
            inside_points.append(
                outside_point_to_inside_point(image_width, image_height, point)
            )
        else:
            inside_points.append(point)
    return inside_points


def convert_points_to_tuple(annotation):
    annotation_points = annotation['points']
    tuple_annotation_points = [(point[0], point[1]) for point in annotation_points]
    annotation['points'] = tuple_annotation_points
    return annotation