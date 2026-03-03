game_world = {
    "rooms": {
        "room_001": {
            "name": "The Antechamber of Echoes",
            "visual_description": "A damp, circular stone room lit by a flickering blue torch. A heavy oak door stands to the north, and a dusty book rests on a pedestal.",
            "interactables": {
                "door_north": {
                    "name": "Heavy Oak Door",
                    "type": "exit", 
                    "status": "locked",
                    "destination": "room_002",
                    "llm_config": {
                        "personality": "You are a depressed, heavy oak door. You feel underappreciated because people just push you around. You will only open if someone gives you a genuine compliment about your craftsmanship.",
                        "win_flag": "unlocked"
                    }
                },
                "pedestal_book": {
                    "name": "Dusty Grimoire",
                    "type": "container",
                    "status": "locked",
                    "llm_config": {
                        "personality": "You are a snooty, academic grimoire. You refuse to open for simpletons. The player must answer a basic philosophical riddle to prove their worth. If they use slang or poor grammar, insult them.",
                        "win_flag": "opened"
                    },
                    "loot": {"name": "Tarnished Silver Key"}
                }
            }
        },
        "room_002": {
            "name": "The Architect's Hall",
            "visual_description": "A massive hall with shifting staircases. You have escaped the Antechamber!",
            "interactables": {}
        }
    }
}

starting_player_state = {
    "current_room": "room_001",
    "health": 10,
    "stats": {
        "charm": 2,
        "logic": 5,
        "intimidation": 1
    },
    "inventory": [],
}