import os
import uuid
from dotenv import load_dotenv
from config.settings import Config
from src.core.runtime import DeepAgentsRuntime

def main():
    load_dotenv()
    
    if not os.getenv("GEMINI_API_KEY"):
        print("Please set GEMINI_API_KEY in your .env file.")
        return

    # Initialize runtime
    runtime = DeepAgentsRuntime()
    
    print("Welcome to the YouTube Content Engine (Multi-Turn Chat)")
    print("Type 'exit' or 'quit' to stop.")
    
    session_id = input("Enter a Session ID (or press Enter to create a new one): ").strip()
    if not session_id:
        session_id = str(uuid.uuid4())
    print(f"Active Session ID: {session_id}\n")

    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            if not user_input.strip():
                continue
            
            print("\nAgent is thinking...")
            response = runtime.invoke(session_id, user_input)
            print(f"\nAgent: {response}")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[Error]: {e}")

if __name__ == "__main__":
    main()
