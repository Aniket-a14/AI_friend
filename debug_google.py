import sys
import os

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

try:
    import google
    print(f"google package path: {google.__path__}")
except ImportError:
    print("Could not import google")

try:
    from google import genai
    print(f"google.genai imported: {genai}")
except ImportError as e:
    print(f"Could not import google.genai: {e}")

try:
    import google_genai
    print(f"google_genai imported: {google_genai}")
except ImportError as e:
    print(f"Could not import google_genai: {e}")

# List site-packages
import site
for path in site.getsitepackages():
    print(f"Site package: {path}")
    google_path = os.path.join(path, "google")
    if os.path.exists(google_path):
        print(f"Contents of {google_path}: {os.listdir(google_path)}")
