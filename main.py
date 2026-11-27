import uuid

from config.settings import Config
from src.core.runtime import DeepAgentsRuntime


def main():
    if not Config.OPENROUTER_API_KEY:
        print("Please set OPENROUTER_API_KEY in your .env file.")
        return

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

            for kind, text in runtime.stream(session_id, user_input):
                if kind == "answer":
                    print(f"\nAgent: {text}")
                else:
                    print(f"  [{kind}] {text}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[Error]: {e}")


if __name__ == "__main__":
    main()
