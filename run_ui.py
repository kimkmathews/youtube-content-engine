import os
import sys
import subprocess

def main():
    """
    Entry point to launch the Streamlit frontend.
    """
    print("Launching YouTube Content Engine Dashboard...")
    
    # Path to the streamlit app script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(script_dir, "ui", "app.py")
    
    if not os.path.exists(app_path):
        print(f"Error: Could not find {app_path}")
        sys.exit(1)
        
    try:
        # Run streamlit
        subprocess.run([sys.executable, "-m", "streamlit", "run", app_path])
    except KeyboardInterrupt:
        print("\nDashboard closed.")
    except Exception as e:
        print(f"Failed to launch Streamlit: {e}")

if __name__ == "__main__":
    main()
