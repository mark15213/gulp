import pathlib
import sys

# gulp_shared is uniquely named, but keep the service dir importable for tests.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
