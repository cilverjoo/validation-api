from PIL import Image
import cairo
import numpy as np


from app.validations.utils.shape import bounds_to_4points


def _normalize_color(r, g, b):
    return r / 255, g / 255, b / 255


def _fill(context, points, rgb):
    r, g, b = rgb

    for i, point in enumerate(points):
        if i == 0:
            context.move_to(point[0], point[1])
        else:
            context.line_to(point[0], point[1])

    context.close_path()
    context.set_source_rgb(b, g, r)
    context.fill()


def generate_masked_image(width, height, color_points_pairs):
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    context = cairo.Context(surface)
    context.set_antialias(cairo.ANTIALIAS_NONE)
    context.set_line_width(1)

    # fill base_color with (255, 255, 255)
    bounds = [(0, 0), (width, height)]
    points = bounds_to_4points(bounds)
    _fill(context=context, points=points, rgb=(1, 1, 1))

    for color_points_pair in color_points_pairs:
        color, points = color_points_pair
        normalized_color = _normalize_color(*color)

        _fill(context=context, points=points, rgb=normalized_color)

    buffer = np.frombuffer(surface.get_data(), dtype=np.uint8).reshape((height, width, 4))[:, :, :3]
    return Image.fromarray(buffer, mode='RGB')


def get_masked_image_from_gt(width, height, annotations, color_map):
    color_points_pairs = []

    for annotation in annotations:
        color_points_pairs.append((color_map[annotation['label']], annotation['points']))

    return generate_masked_image(width=width, height=height, color_points_pairs=color_points_pairs)


def has_hollow_point(image: Image, available_colors, base_color=None):
    width, height = image.size
    pixels = image.load()
    for x in range(width):
        for y in range(height):
            pixel = pixels[x, y]

            if base_color:
                if pixel == base_color:
                    return True
            else:
                if pixel not in available_colors:
                    return True

    return False
