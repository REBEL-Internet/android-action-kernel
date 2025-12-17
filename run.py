from kernel import run_agent
import sys

def read_prompt_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except Exception as e:
        print(f"Error reading prompt file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python run.py <device_serial> [prompt_file]")
        print("  device_serial: Serial number of the Android device")
        print("  prompt_file:   Path to a file containing the prompt/instruction")
        sys.exit(1)
    
    device_serial = sys.argv[1]
    
    # Read prompt from file if provided, otherwise use default
    if len(sys.argv) >= 3:
        prompt_file = sys.argv[2]
        goal = read_prompt_from_file(prompt_file)
    else:
        print("\n🎯 Enter your goal (e.g., 'Open Apple music app and play any song'):")
        goal = input("> ")
    
    run_agent(goal, device_serial)