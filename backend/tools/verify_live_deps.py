try:
    import google.genai
    import websockets
    print("✅ Dependencies verified.")
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
