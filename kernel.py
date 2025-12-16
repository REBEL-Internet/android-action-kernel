import os
import time
import subprocess
import json
from typing import Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv
import sanitizer

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
ADB_PATH = "adb"  # Ensure adb is in your PATH
MODEL = "gpt-4o"  # Or "gpt-4-turbo" for faster/cheaper execution
SCREEN_DUMP_PATH = "/sdcard/window_dump.xml"
LOCAL_DUMP_PATH = "window_dump.xml"

# Initialize OpenAI client with API key from environment variables
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables. Please create a .env file with your API key.")

client = OpenAI(api_key=api_key)

def list_android_devices() -> List[Dict[str, str]]:
    """List all connected Android devices."""
    result = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Failed to list devices: {result.stderr}")
        return []
    
    devices = []
    lines = result.stdout.strip().split('\n')[1:]  # Skip first line
    for line in lines:
        if line.strip() and '\t' in line:
            serial, status = line.strip().split('\t')
            if status == 'device':
                devices.append({
                    'serial': serial,
                    'status': status,
                    'model': get_device_model(serial) or 'Unknown Model'
                })
    return devices

def get_device_model(serial: str) -> str:
    """Get the model name of the device."""
    result = subprocess.run(
        [ADB_PATH, '-s', serial, 'shell', 'getprop', 'ro.product.model'],
        capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""

def run_adb_command(command: List[str], device_serial: str = None):
    """
    Executes a shell command via ADB.
    
    Args:
        command: List of command arguments
        device_serial: Optional device serial number to target specific device
    """
    adb_cmd = [ADB_PATH]
    if device_serial:
        adb_cmd.extend(['-s', device_serial])
    adb_cmd.extend(command)
    
    result = subprocess.run(adb_cmd, capture_output=True, text=True)
    if result.stderr and "error" in result.stderr.lower():
        print(f"❌ ADB Error: {result.stderr.strip()}")
    return result.stdout.strip()

def get_screen_state(device_serial: str = None) -> str:
    """Dumps the current UI XML and returns the sanitized JSON string."""
    # 1. Capture XML
    run_adb_command(["shell", "uiautomator", "dump", SCREEN_DUMP_PATH], device_serial)
    
    # 2. Pull to local
    run_adb_command(["pull", SCREEN_DUMP_PATH, LOCAL_DUMP_PATH])
    
    # 3. Read & Sanitize
    if not os.path.exists(LOCAL_DUMP_PATH):
        return "Error: Could not capture screen."
        
    with open(LOCAL_DUMP_PATH, "r", encoding="utf-8") as f:
        xml_content = f.read()
        
    elements = sanitizer.get_interactive_elements(xml_content)
    return json.dumps(elements, indent=2)

def execute_action(action: Dict[str, Any], device_serial: str = None):
    """
    Executes the action decided by the LLM.
    
    Args:
        action: Dictionary containing action details
        device_serial: Optional device serial number to target specific device
    """
    act_type = action.get("action")
    
    if act_type == "tap":
        x, y = action.get("coordinates")
        print(f"👉 Tapping: ({x}, {y})")
        run_adb_command(["shell", "input", "tap", str(x), str(y)], device_serial)
        
    elif act_type == "type":
        text = action.get("text").replace(" ", "%s")  # ADB requires %s for spaces
        print(f"⌨️ Typing: {action.get('text')}")
        run_adb_command(["shell", "input", "text", text], device_serial)
        
    elif act_type == "home":
        print("🏠 Going Home")
        run_adb_command(["shell", "input", "keyevent", "KEYCODE_HOME"], device_serial)
        
    elif act_type == "back":
        print("🔙 Going Back")
        run_adb_command(["shell", "input", "keyevent", "KEYCODE_BACK"], device_serial)
        
    elif act_type == "wait":
        print("⏳ Waiting...")
        time.sleep(2)
        
    elif act_type == "done":
        print("✅ Goal Achieved.")
        exit(0)

def get_llm_decision(goal: str, screen_context: str) -> Dict[str, Any]:
    """Sends screen context to LLM and asks for the next move."""
    system_prompt = """
    You are an Android Driver Agent. Your job is to achieve the user's goal by navigating the UI.
    
    You will receive:
    1. The User's Goal.
    2. A list of interactive UI elements (JSON) with their (x,y) center coordinates.
    
    You must output ONLY a valid JSON object with your next action.
    
    Available Actions:
    - {"action": "tap", "coordinates": [x, y], "reason": "Why you are tapping"}
    - {"action": "type", "text": "Hello World", "reason": "Why you are typing"}
    - {"action": "home", "reason": "Go to home screen"}
    - {"action": "back", "reason": "Go back"}
    - {"action": "wait", "reason": "Wait for loading"}
    - {"action": "done", "reason": "Task complete"}
    
    Example Output:
    {"action": "tap", "coordinates": [540, 1200], "reason": "Clicking the 'Connect' button"}
    """
    
    response = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"GOAL: {goal}\n\nSCREEN_CONTEXT:\n{screen_context}"}
        ]
    )
    
    return json.loads(response.choices[0].message.content)

def run_agent(goal: str, device_serial: str = None, max_steps=10):
    """
    Run the Android agent to achieve the specified goal.
    
    Args:
        goal: The goal to achieve
        device_serial: Optional device serial number to target specific device
        max_steps: Maximum number of steps to attempt
    """
    print(f"🚀 Android Use Agent Started. Goal: {goal}")
    if device_serial:
        print(f"📱 Targeting device: {device_serial}")
    
    for step in range(max_steps):
        print(f"\n--- Step {step + 1} ---")
        
        # 1. Perception
        print("👀 Scanning Screen...")
        screen_context = get_screen_state(device_serial)
        
        # 2. Reasoning
        print("🧠 Thinking...")
        decision = get_llm_decision(goal, screen_context)
        print(f"💡 Decision: {decision.get('reason')}")
        
        # 3. Action
        execute_action(decision, device_serial)
        
        # Wait for UI to update
        time.sleep(2)

def select_device() -> str:
    """Prompt user to select a device from the list of connected devices."""
    devices = list_android_devices()
    
    if not devices:
        print("❌ No devices found. Please connect a device and try again.")
        exit(1)
        
    if len(devices) == 1:
        print(f"🔍 Found 1 device: {devices[0]['model']} ({devices[0]['serial']})")
        return devices[0]['serial']
    
    print("\n📱 Connected Devices:")
    for i, device in enumerate(devices, 1):
        print(f"{i}. {device['model']} ({device['serial']})")
    
    while True:
        try:
            choice = input(f"\nSelect a device (1-{len(devices)}): ")
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx]['serial']
            print(f"Please enter a number between 1 and {len(devices)}")
        except ValueError:
            print("Please enter a valid number.")

if __name__ == "__main__":
    # Select device
    device_serial = select_device()
    
    # Get goal from user
    print("\n🎯 Enter your goal (e.g., 'Open settings and turn on Wi-Fi'):")
    goal = input("> ")
    
    # Run the agent
    run_agent(goal, device_serial)