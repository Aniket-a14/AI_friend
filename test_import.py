try:
    from google import genai
    print("Import successful!")
    client = genai.Client(api_key="test")
    print("Client created.")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
