import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


helper = load("cctv_control_helper", ROOT / "app" / "cctv_control_helper.py")
control = load("cctv_control", ROOT / "app" / "cctv_control.py")


class SecurityBoundaryTests(unittest.TestCase):
    def test_media_identifier_round_trip(self):
        relative = "Camera-1/2026/10/15/example recording.mkv"
        self.assertEqual(control.decode_id(control.b64_id(relative)), relative)

    def test_safe_relative_accepts_managed_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            candidate = helper.safe_relative("camera/clip.mkv", root)
            self.assertEqual(candidate, root / "camera" / "clip.mkv")

    def test_safe_relative_rejects_escape_and_absolute(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for value in ("../outside.mkv", "/etc/passwd", "camera/../../outside.mkv"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    helper.safe_relative(value, root)

    def test_safe_relative_rejects_symlink_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "real.mkv"
            target.touch()
            (root / "link.mkv").symlink_to(target)
            with self.assertRaises(ValueError):
                helper.safe_relative("link.mkv", root)


if __name__ == "__main__":
    unittest.main()
