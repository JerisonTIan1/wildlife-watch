"""Preview OpenCV-compatible inputs. This module performs no detection or fusion."""

import argparse
import sys
from contextlib import ExitStack
from pathlib import Path

import cv2


def source(value):
    """Numeric arguments are camera indices; all other values must be local files."""
    if value.isdecimal():
        return int(value)
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"Video file not found: {value}")
    return str(path.resolve())


def panel(frame, label):
    height, width = frame.shape[:2]
    scale = min(640 / width, 480 / height)
    resized = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))))
    h, w = resized.shape[:2]
    canvas = cv2.copyMakeBorder(resized, 0, 480 - h, 0, 640 - w, cv2.BORDER_CONSTANT)
    cv2.rectangle(canvas, (0, 0), (640, 34), (0, 0, 0), -1)
    cv2.putText(canvas, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    return canvas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rgb', type=source, default=0, help='Camera index or local video path')
    parser.add_argument('--thermal', type=source, help='Optional compatible camera index or local video path')
    parser.add_argument('--headless', action='store_true', help='Read frames without opening a display')
    parser.add_argument('--max-frames', type=int, default=0, help='Stop after N frame sets; 0 means unlimited')
    args = parser.parse_args(argv)
    if args.max_frames < 0:
        parser.error('--max-frames must be nonnegative')
    if args.thermal == args.rgb:
        parser.error('RGB and thermal must use different sources')
    inputs = [('RGB', args.rgb)]
    if args.thermal is not None:
        inputs.append(('THERMAL VIDEO', args.thermal))
    count = 0
    with ExitStack() as cleanup:
        cleanup.callback(cv2.destroyAllWindows)
        captures = []
        for name, value in inputs:
            cap = cv2.VideoCapture(value)
            cleanup.callback(cap.release)
            if not cap.isOpened():
                print(f'{name}: unable to open input. Check device index, connection, or file codec.', file=sys.stderr)
                return 1
            captures.append((name, value, cap))
        print('PREVIEW ONLY: no wildlife detector, synchronization, or alerts. Q/Escape exits.')
        while True:
            frames = []
            for name, value, cap in captures:
                ok, frame = cap.read()
                if not ok or frame is None:
                    if isinstance(value, int):
                        print(f'{name}: camera read failed after {count} complete frame sets.', file=sys.stderr)
                        return 1
                    print(f'{name}: file ended or could not be decoded after {count} complete frame sets.')
                    return 0 if count else 1
                if not args.headless:
                    frames.append(panel(frame, name + ' | PREVIEW ONLY'))
            count += 1
            if not args.headless:
                cv2.imshow('Wildlife Watch - unsynchronized preview', cv2.hconcat(frames))
                if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
                    break
            if args.max_frames and count >= args.max_frames:
                break
        print(f'Preview finished: {count} complete frame sets.')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
