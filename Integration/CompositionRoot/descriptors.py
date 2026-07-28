"""Immutable OpenCV and dependency-free visual descriptor extraction."""
from math import pi

from taskgraph_vision import FeatureDescriptor


def component_features(area, perimeter, width, height, center_x, center_y, texture, edge_density, corners, contrast, confidence):
    aspect = width / max(height, 1); circularity = 4 * pi * area / max(perimeter * perimeter, 1); compactness = perimeter * perimeter / max(area, 1)
    return (
        FeatureDescriptor("geometry", (area, perimeter, aspect, center_x, center_y, circularity, compactness)),
        FeatureDescriptor("appearance", (texture, edge_density, float(corners), contrast)),
        FeatureDescriptor("scores", (circularity, texture, contrast, 0.0, confidence, confidence)),
        FeatureDescriptor("motion_vector", (0.0, 0.0)),
    )


def opencv_descriptors(color, gray, contour, region):
    import cv2
    import numpy as np
    x, y, width, height = region; crop_color = color[y:y+height, x:x+width]; crop = gray[y:y+height, x:x+width]
    moments = cv2.moments(contour); hu = tuple(float(value) for value in cv2.HuMoments(moments).flatten())
    orb = cv2.ORB_create(nfeatures=64); keypoints, orb_values = orb.detectAndCompute(crop, None)
    orb_summary = () if orb_values is None else tuple(float(value) / 255.0 for value in orb_values.mean(axis=0)[:16])
    histograms = []
    for channel in range(3):
        hist = cv2.calcHist([crop_color], [channel], None, [8], [0, 256]); cv2.normalize(hist, hist); histograms.extend(float(value) for value in hist.flatten())
    dominant = tuple(float(value) / 255.0 for value in crop_color.reshape(-1, 3).mean(axis=0))
    gradients_x = cv2.Sobel(crop, cv2.CV_32F, 1, 0); gradients_y = cv2.Sobel(crop, cv2.CV_32F, 0, 1); magnitude = cv2.magnitude(gradients_x, gradients_y)
    return (
        FeatureDescriptor("orb", orb_summary), FeatureDescriptor("hu_moments", hu),
        FeatureDescriptor("color_histogram", tuple(histograms)), FeatureDescriptor("dominant_colors", dominant),
        FeatureDescriptor("gradient_statistics", (float(magnitude.mean()) / 255.0, float(magnitude.std()) / 255.0)),
        FeatureDescriptor("corner_density", (len(keypoints) / max(width * height, 1),)),
    )
