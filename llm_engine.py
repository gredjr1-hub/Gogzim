import re
import json
import random
from google import genai
import streamlit as st
from openai import OpenAI

# Initialize APIs from Streamlit Secrets
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
image_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def generate_location_image(prompt_text):
    """Calls DALL-E 3 with a highly specific prompt to ensure POIs are visible."""
    style_suffix = " First-person perspective, highly detailed video game concept art, moody lighting, clear focal points."
    full_prompt = f"{prompt_text} {style_suffix}"
    
    try:
        response = image_client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url
    except Exception as e:
        print(f"Image generation failed: {e}")
        return None

def generate_dynamic_escape_room(theme, difficulty):
    """Forces the LLM to generate theme-specific starting tools and bind them to puzzles."""
    configs = {
        "Easy": {"digits": 2, "total_objs": 3},
        "Normal": {"digits": 3, "total_objs": 4},
        "Hard": {"digits": 4, "total_objs": 5}
    }
    config = configs.get(difficulty, configs["Normal"])
    num_digits = config["digits"]
    total_objects = config["total_objs"]

    master_code = "".join([str(random.randint(0, 9)) for _ in range(num_digits)])

    prompt = f"""
    You are an expert real-world escape room designer. 
    Design a single-room escape experience based on this theme: "{theme}".
    The Difficulty level is: {difficulty}.

    ---THE MASTER PUZZLE---
    The players must find a {num_digits}-digit numerical code to unlock the final door.
    The strictly defined solution code is: {master_code}

    ---DESIGN CONSTRAINTS---
    1. **Starting Inventory:** Generate exactly 3 starting items/tools the player begins with. These items MUST be highly specific and contextually relevant to the "{theme}" theme.
    2. **The Objects:** Create exactly {total_objects} unique interactable objects in the room.
    3. **Mandatory Use Condition:** At least ONE of the interactable objects MUST explicitly require the player to USE one of the 3 starting items to solve it. 
    4. **In-Room Chain:** Another object must yield a new physical tool, and a different object must require that new tool.
    5. **Loot:** All {num_digits} digits of the master code must be hidden across these objects.

    Output strictly valid JSON following this exact structure:
    {{
        "name": "Creative Room Title",
        "visual_description": "Two vivid sentences describing the room.",
        "starting_items": [
            {{"name": "Tool Name 1", "description": "What it looks like."}},
            {{"name": "Tool Name 2", "description": "What it looks like."}},
            {{"name": "Tool Name 3", "description": "What it looks like."}}
        ],
        "master_puzzle": {{
            "type": "keypad",
            "solution": "{master_code}",
            "solved": false,
            "success_message": "The keypad beeps green and the door unlocks!"
        }},
        "interactables": {{
            "unique_id_1": {{
                "name": "Name of Object",
                "status": "active",
                "llm_config": {{
                    "personality": "Describe how this object behaves. Explicitly state if it requires a specific tool to open/activate, or if it requires a riddle to be solved.",
                    "win_flag": "yielded_loot"
                }},
                "loot": {{
                    "type": "item", 
                    "name": "Name of Loot",
                    "description": "Physical item or clue text."
                }}
            }}
            // Repeat for all {total_objects} objects...
        }}
    }}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Escape Room Generation Error: {e}")
        return None

def build_system_prompt(player_state, obj_data):
    """Handles both rigid buttons and custom text inputs."""
    llm_config = obj_data["llm_config"]
    win_flag = llm_config["win_flag"]
    
    inv_list = [item["name"] for item in player_state["inventory"]]
    inv_string = ", ".join(inv_list) if inv_list else "Nothing"

    json_example = f"```json\n{{\n    \"{win_flag}\": true\n}}\n```"

    system_prompt = f"""
You are an entity/mechanism in an escape room.
YOUR PUZZLE ROLE & WIN CONDITION: {llm_config['personality']}
THE PLAYER'S INVENTORY: [{inv_string}]

The player will interact using either rigid commands (OBSERVE, TOUCH, USE, HINT) OR custom text.
1. If OBSERVE: Describe your appearance in detail. Do NOT solve the puzzle.
2. If TOUCH: Describe the physical reaction. Only yield your loot if physical touching/opening is the specific solution.
3. If HINT: Provide a cryptic, subtle clue about what item or action is needed. Do NOT solve it for them.
4. If USE: The player will specify an item. Check your instructions. If that exact item solves your puzzle, you MUST yield. If it's the wrong item, tell them nothing happens.
5. If CUSTOM ACTION/SPEECH: Evaluate what the player types. If they logically solve your riddle, creatively and accurately use an item they possess, or perform a valid physical action that meets your win condition, you must yield. If they try to cheat, break the rules, or just demand the answer, deny them in character.

If the player successfully solves you, append this exact JSON block to the end of your text:
{json_example}
"""
    return system_prompt.strip()

def interact_with_entity(system_prompt, user_action):
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_prompt}\n\nPlayer Action: {user_action}"
        )
        return response.text
    except Exception as e:
        return f"Error: {e}"

def parse_llm_response(text, win_flag):
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    dialogue = text
    game_logic = {win_flag: False}
    
    if match:
        json_str = match.group(1)
        dialogue = text.replace(match.group(0), "").strip()
        try:
            parsed_data = json.loads(json_str)
            game_logic[win_flag] = parsed_data.get(win_flag, False)
        except json.JSONDecodeError:
            pass
            
    return dialogue, game_logic