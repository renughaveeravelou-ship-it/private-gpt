import os
import json
import logging
import uuid
import datetime
from pathlib import Path
from injector import inject, singleton

logger = logging.getLogger(__name__)

MEMORY_FILE_PATH = Path("local_data/private_gpt/user_memory.json")

DEFAULT_PROFILE = {
    "user_name": "User",
    "role": "Researcher",
    "theme_preset": "Midnight Aurora",
    "interests": ["Artificial Intelligence", "Document Search"],
    "explicit_preferences": {
        "tone": "Adaptive",
        "detail_level": "Medium",
        "custom_instructions": ""
    },
    "learned_facts": [
        "User prefers explanations with practical examples.",
        "User is working on analyzing complex document archives."
    ],
    "stats": {
        "total_queries": 0,
        "total_sessions": 0,
        "total_tokens_estimated": 0
    }
}

@singleton
class MemoryService:
    @inject
    def __init__(self) -> None:
        self.memory_file = MEMORY_FILE_PATH
        # Ensure directories exist
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_memory()

    def _load_memory(self) -> None:
        if not self.memory_file.exists():
            self.data = {
                "profile": DEFAULT_PROFILE.copy(),
                "conversations": {}
            }
            self._save_memory()
        else:
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                # Safeguards for unexpected schema mismatches
                if "profile" not in self.data:
                    self.data["profile"] = DEFAULT_PROFILE.copy()
                if "conversations" not in self.data:
                    self.data["conversations"] = {}
            except Exception as e:
                logger.error(f"Error loading memory file: {e}. Resetting memory data.")
                self.data = {
                    "profile": DEFAULT_PROFILE.copy(),
                    "conversations": {}
                }
                self._save_memory()

    def _save_memory(self) -> None:
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory file: {e}")

    # --- Profile & Preferences Management ---

    def get_profile(self) -> dict:
        self._load_memory()
        return self.data.get("profile", DEFAULT_PROFILE)

    def save_profile(self, profile: dict) -> None:
        self.data["profile"] = profile
        self._save_memory()

    def update_explicit_preferences(self, tone: str, detail_level: str, custom_instructions: str) -> None:
        profile = self.get_profile()
        profile["explicit_preferences"]["tone"] = tone
        profile["explicit_preferences"]["detail_level"] = detail_level
        profile["explicit_preferences"]["custom_instructions"] = custom_instructions
        self.save_profile(profile)

    def update_user_details(self, name: str, role: str) -> None:
        profile = self.get_profile()
        profile["user_name"] = name
        profile["role"] = role
        self.save_profile(profile)

    def add_learned_fact(self, fact: str) -> None:
        profile = self.get_profile()
        if fact and fact not in profile.get("learned_facts", []):
            profile.setdefault("learned_facts", []).append(fact)
            self.save_profile(profile)

    def delete_learned_fact(self, fact: str) -> None:
        profile = self.get_profile()
        facts = profile.get("learned_facts", [])
        if fact in facts:
            facts.remove(fact)
            profile["learned_facts"] = facts
            self.save_profile(profile)

    # --- User Preference & Topic Learning (AI Adaptive Learning) ---

    def learn_from_interaction(self, user_msg: str, bot_msg: str) -> None:
        profile = self.get_profile()
        profile["stats"]["total_queries"] = profile["stats"].get("total_queries", 0) + 1
        
        # Simple heuristic topic detection
        msg_lower = user_msg.lower()
        new_interests = set(profile.setdefault("interests", []))
        
        if any(w in msg_lower for w in ["excel", "sheet", "csv", "table", "row", "column", "revenue"]):
            new_interests.add("Data Analysis")
        if any(w in msg_lower for w in ["code", "python", "javascript", "programming", "bug", "write a function"]):
            new_interests.add("Software Engineering")
        if any(w in msg_lower for w in ["neural", "cnn", "deep learning", "training", "weights", "easyocr", "ocr"]):
            new_interests.add("Deep Learning")
        if any(w in msg_lower for w in ["summarize", "tldr", "brief", "short summary"]):
            new_interests.add("Summarization Techniques")
            
        profile["interests"] = list(new_interests)

        # Dynamic heuristic learning of user preferences/style instructions
        learned_facts = profile.setdefault("learned_facts", [])
        if "be brief" in msg_lower or "tldr" in msg_lower or "short response" in msg_lower:
            fact = "User prefers short and concise answers."
            if fact not in learned_facts:
                learned_facts.append(fact)
        elif "in detail" in msg_lower or "step-by-step" in msg_lower or "verbose" in msg_lower:
            fact = "User prefers in-depth, step-by-step explanations."
            if fact not in learned_facts:
                learned_facts.append(fact)
        elif "bullet point" in msg_lower:
            fact = "User prefers structured responses using bullet points."
            if fact not in learned_facts:
                learned_facts.append(fact)
                
        self.save_profile(profile)

    # --- Dynamic System Prompt Compiler (Adaptive Learning Suffix) ---

    def compile_adaptive_prompt(self, base_prompt: str) -> str:
        profile = self.get_profile()
        prefs = profile.get("explicit_preferences", {})
        
        suffix = "\n\n[Personalization & Context]"
        suffix += f"\n- User Name: {profile.get('user_name', 'User')}"
        suffix += f"\n- User Role: {profile.get('role', 'Researcher')}"
        
        tone = prefs.get("tone", "Adaptive")
        detail = prefs.get("detail_level", "Medium")
        if tone != "Adaptive":
            suffix += f"\n- Response Tone: {tone}"
        if detail != "Medium":
            suffix += f"\n- Detail Level: {detail}"
            
        custom_inst = prefs.get("custom_instructions", "")
        if custom_inst:
            suffix += f"\n- Custom User Directive: {custom_inst}"
            
        learned = profile.get("learned_facts", [])
        if learned:
            suffix += "\n- Learned details about User preferences:\n"
            suffix += "\n".join(f"  * {fact}" for fact in learned)
            
        return base_prompt + suffix

    # --- Smart Context-Aware Recommendations ---

    def get_recommendations(self, current_chat_history: list) -> list[str]:
        if not current_chat_history:
            return [
                "Summarize my active documents.",
                "Compare the key concepts in the uploaded files.",
                "What are the main insights or takeaways here?"
            ]
        
        # Get the last user message to suggest context-aware questions
        last_user_msg = ""
        for msg in reversed(current_chat_history):
            # Gradio history is list of list [user, bot]
            if isinstance(msg, list) and len(msg) > 0 and msg[0]:
                last_user_msg = msg[0].lower()
                break
        
        if not last_user_msg:
            return ["Can you extract the main action items?", "Provide a detailed summary."]

        if any(w in last_user_msg for w in ["revenue", "sheet", "csv", "finance", "dollar", "q4", "expense"]):
            return [
                "Can you show a breakdown of the quarterly values?",
                "What are the key trends indicated by this data?",
                "Explain the data analysis summary."
            ]
        if any(w in last_user_msg for w in ["deep learning", "neural", "cnn", "image", "ocr", "style"]):
            return [
                "What neural network features are described here?",
                "Compare CNNs with standard machine learning approaches.",
                "Give me a step-by-step breakdown of deep learning."
            ]
        
        return [
            "Explain that in more detail.",
            "Can you write a concise summary of that response?",
            "What are the related topics of interest here?"
        ]

    # --- Previous Conversation Recall (History Management) ---

    def list_conversations(self) -> list[dict]:
        self._load_memory()
        convs = []
        for cid, info in self.data.get("conversations", {}).items():
            convs.append({
                "id": cid,
                "title": info.get("title", "Untitled Chat"),
                "timestamp": info.get("timestamp", "")
            })
        # Sort by timestamp descending
        convs.sort(key=lambda x: x["timestamp"], reverse=True)
        return convs

    def get_conversation(self, conv_id: str) -> list[list[str]]:
        self._load_memory()
        conv = self.data.get("conversations", {}).get(conv_id, {})
        return conv.get("messages", [])

    def save_conversation(self, conv_id: str, title: str, messages: list[list[str]]) -> None:
        self._load_memory()
        if not title and messages:
            # Auto-generate title from first user message
            first_user = messages[0][0]
            title = first_user[:30] + "..." if len(first_user) > 30 else first_user
            
        timestamp = datetime.datetime.now().isoformat()
        
        self.data["conversations"][conv_id] = {
            "id": conv_id,
            "title": title or "Untitled Session",
            "timestamp": timestamp,
            "messages": messages
        }
        
        # Track session statistic directly from in-memory profile to avoid reload overwrite
        profile = self.data.setdefault("profile", DEFAULT_PROFILE.copy())
        profile["stats"]["total_sessions"] = len(self.data["conversations"])
        self._save_memory()

    def delete_conversation(self, conv_id: str) -> None:
        self._load_memory()
        if conv_id in self.data.get("conversations", {}):
            del self.data["conversations"][conv_id]
            
            # Recalculate sessions directly from in-memory profile to avoid reload overwrite
            profile = self.data.setdefault("profile", DEFAULT_PROFILE.copy())
            profile["stats"]["total_sessions"] = len(self.data.get("conversations", {}))
            self._save_memory()
