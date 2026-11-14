"""Reproducible synthetic A/B benchmark, not evidence of physical-camera reliability."""

from collections import defaultdict
from time import perf_counter

import cv2
import numpy as np

from .aruco_webcam import detect_target, make_detector


def samples():
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    for size in (36, 70, 140):
        image = np.full((480, 640, 3), 255, np.uint8)
        marker = cv2.aruco.generateImageMarker(dictionary, 0, size)
        image[180:180 + size, 250:250 + size] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        yield "clean", image, True
        for length in (3, 7, 13, 21):
            kernel = np.zeros((length, length), np.float32)
            kernel[length // 2, :] = 1 / length
            yield "motion_blur", cv2.filter2D(image, -1, kernel), True
        for contrast in (0.03, 0.08, 0.2):
            yield "low_contrast", (image.astype(float) * contrast + 100).astype(np.uint8), True
        for sigma in (1, 2, 4):
            yield "defocus", cv2.GaussianBlur(image, (0, 0), sigma), True
        occluded = image.copy()
        occluded[180:180 + size // 3, 250:250 + size] = 255
        yield "occlusion", occluded, True
    yield "negative", np.full((480, 640, 3), 255, np.uint8), False
    for marker_id in (1, 5, 49):
        image = np.full((480, 640, 3), 255, np.uint8)
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 100)
        image[180:280, 250:350] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        yield "negative", image, False


def main():
    # Single-threaded timing reduces scheduler noise; only this benchmark changes it.
    cv2.setNumThreads(1)
    corpus = list(samples())
    print(f"OpenCV {cv2.__version__}; {len(corpus)} synthetic 640x480 frames; single thread; 3 passes")
    print("profile,preprocess,category,detected,total,median_ms,p95_ms")
    for profile, preprocessing in (("baseline", "none"), ("wide", "none"),
                                   ("baseline", "clahe"), ("wide", "clahe")):
        detector = make_detector(profile)
        preprocess = cv2.createCLAHE(2.0, (8, 8)) if preprocessing == "clahe" else None
        for _, frame, _ in corpus:
            detect_target(frame, detector, preprocess)  # warmup
        results = defaultdict(list)
        for _ in range(3):
            for category, frame, _ in corpus:
                start = perf_counter()
                _, center, _ = detect_target(frame, detector, preprocess)
                results[category].append((center is not None, (perf_counter() - start) * 1000))
        for category, values in results.items():
            durations = [v[1] for v in values]
            print(f"{profile},{preprocessing},{category},{sum(v[0] for v in values)},{len(values)},"
                  f"{np.median(durations):.2f},{np.percentile(durations, 95):.2f}")
    print("Negative detections are false positives. Repeated synthetic frames are not independent trials.")


if __name__ == "__main__":
    main()
