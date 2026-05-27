"""This file should be imported if and only if you want to run the UI locally."""

import base64
import logging
import time
import uuid
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from typing import Any

import gradio as gr  # type: ignore
from fastapi import FastAPI
from gradio.themes.utils.colors import slate  # type: ignore
from injector import inject, singleton
from llama_index.core.llms import ChatMessage, ChatResponse, MessageRole
from llama_index.core.types import TokenGen
from pydantic import BaseModel

from private_gpt.constants import PROJECT_ROOT_PATH
from private_gpt.di import global_injector
from private_gpt.open_ai.extensions.context_filter import ContextFilter
from private_gpt.server.chat.chat_service import ChatService, CompletionGen
from private_gpt.server.chunks.chunks_service import Chunk, ChunksService
from private_gpt.server.ingest.ingest_service import IngestService
from private_gpt.server.recipes.summarize.summarize_service import SummarizeService
from private_gpt.settings.settings import settings
from private_gpt.ui.images import logo_svg
from private_gpt.components.memory.memory_service import MemoryService

logger = logging.getLogger(__name__)

# Premium glassmorphic, neumorphic, and gradient theme stylesheets
THEME_PRESETS = {
    "Midnight Aurora": """
        body, .gradio-container {
            background: linear-gradient(-45deg, #0b0f19, #1a103c, #2b0b30, #080d1a) !important;
            background-size: 400% 400% !important;
            animation: gradientBG 15s ease infinite !important;
            color: #e2e8f0 !important;
        }
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        /* Frosted Glassmorphism Panel styles */
        .block, .accordion, .glass-panel, .form, .tab-nav {
            background: rgba(255, 255, 255, 0.03) !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 12px !important;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important;
            transition: all 0.3s ease !important;
        }
        .tab-nav button.selected {
            background-color: rgba(199, 186, 255, 0.15) !important;
            border-bottom: 2px solid #C7BAFF !important;
            color: #C7BAFF !important;
            text-shadow: 0 0 8px rgba(199, 186, 255, 0.5) !important;
        }
        button, button.primary {
            transition: all 0.2s ease !important;
        }
        button:hover, button.primary:hover {
            transform: translateY(-2px) !important;
        }
    """,
    "Ocean Mist": """
        body, .gradio-container {
            background: linear-gradient(-45deg, #0f2b30, #0a1f26, #16362d, #081a1c) !important;
            background-size: 400% 400% !important;
            animation: gradientBG 15s ease infinite !important;
            color: #e6f1f5 !important;
        }
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        .block, .accordion, .glass-panel, .form, .tab-nav {
            background: rgba(255, 255, 255, 0.02) !important;
            backdrop-filter: blur(16px) !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            border-radius: 12px !important;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
        }
        .tab-nav button.selected {
            background-color: rgba(45, 212, 191, 0.15) !important;
            border-bottom: 2px solid #2dd4bf !important;
            color: #2dd4bf !important;
        }
        button.primary {
            background: linear-gradient(135deg, #2dd4bf 0%, #0d9488 100%) !important;
            border: none !important;
            color: #0a1f26 !important;
            font-weight: bold !important;
            box-shadow: 0 4px 15px rgba(13, 148, 136, 0.4) !important;
        }
        button.primary:hover {
            transform: translateY(-2px) !important;
        }
    """,
    "Neumorphic Slate": """
        body, .gradio-container {
            background-color: #e0e5ec !important;
            color: #313b3c !important;
        }
        .dark body, .dark .gradio-container {
            background-color: #1b2028 !important;
            color: #a0aec0 !important;
        }
        /* Soft double shadow Neumorphism layout styles */
        .block, .accordion, .glass-panel, .form, .tab-nav {
            background: #e0e5ec !important;
            border: none !important;
            border-radius: 16px !important;
            box-shadow: 9px 9px 16px #bcbfc6, -9px -9px 16px #ffffff !important;
            transition: all 0.3s ease !important;
        }
        .dark .block, .dark .accordion, .dark .glass-panel, .dark .form, .dark .tab-nav {
            background: #1b2028 !important;
            box-shadow: 9px 9px 16px #111419, -9px -9px 16px #252c37 !important;
        }
        button, button.primary {
            background: #e0e5ec !important;
            color: #313b3c !important;
            border: none !important;
            border-radius: 12px !important;
            box-shadow: 4px 4px 8px #bcbfc6, -4px -4px 8px #ffffff !important;
        }
        .dark button, .dark button.primary {
            background: #1b2028 !important;
            color: #a0aec0 !important;
            box-shadow: 4px 4px 8px #111419, -4px -4px 8px #252c37 !important;
        }
        button:hover, button.primary:hover {
            box-shadow: inset 2px 2px 5px #bcbfc6, inset -2px -2px 5px #ffffff !important;
            transform: scale(0.98) !important;
        }
        .dark button:hover, .dark button.primary:hover {
            box-shadow: inset 2px 2px 5px #111419, inset -2px -2px 5px #252c37 !important;
        }
    """,
    "Cyberpunk Neon": """
        body, .gradio-container {
            background-color: #030008 !important;
            background-image: radial-gradient(circle at 50% 50%, #150025 0%, #030008 100%) !important;
            color: #00ffcc !important;
            font-family: 'Courier New', monospace !important;
        }
        .block, .accordion, .glass-panel, .form, .tab-nav {
            background: #0d0214 !important;
            border: 1px solid #ff007f !important;
            border-radius: 4px !important;
            box-shadow: 0 0 10px rgba(255, 0, 127, 0.3) !important;
        }
        .tab-nav button.selected {
            background-color: #ff007f !important;
            color: #000000 !important;
            text-shadow: none !important;
            box-shadow: 0 0 15px #ff007f !important;
        }
        button, button.primary {
            background: transparent !important;
            color: #00ffcc !important;
            border: 1px solid #00ffcc !important;
            border-radius: 4px !important;
            box-shadow: 0 0 8px rgba(0, 255, 204, 0.2) !important;
            text-transform: uppercase !important;
            letter-spacing: 1px !important;
        }
        button:hover, button.primary:hover {
            background: #00ffcc !important;
            color: #030008 !important;
            box-shadow: 0 0 15px #00ffcc !important;
            transform: scale(1.05) !important;
        }
    """
}

THIS_DIRECTORY_RELATIVE = Path(__file__).parent.relative_to(PROJECT_ROOT_PATH)
AVATAR_BOT = THIS_DIRECTORY_RELATIVE / "avatar-bot.ico"

UI_TAB_TITLE = "My Private GPT"
SOURCES_SEPARATOR = "<hr>Sources: \n"


class Modes(str, Enum):
    RAG_MODE = "RAG"
    SEARCH_MODE = "Search"
    BASIC_CHAT_MODE = "Basic"
    SUMMARIZE_MODE = "Summarize"


MODES: list[Modes] = [
    Modes.RAG_MODE,
    Modes.SEARCH_MODE,
    Modes.BASIC_CHAT_MODE,
    Modes.SUMMARIZE_MODE,
]


class Source(BaseModel):
    file: str
    page: str
    text: str

    class Config:
        frozen = True

    @staticmethod
    def curate_sources(sources: list[Chunk]) -> list["Source"]:
        curated_sources = []
        for chunk in sources:
            doc_metadata = chunk.document.doc_metadata
            file_name = doc_metadata.get("file_name", "-") if doc_metadata else "-"
            page_label = doc_metadata.get("page_label", "-") if doc_metadata else "-"
            source = Source(file=file_name, page=page_label, text=chunk.text)
            curated_sources.append(source)
            curated_sources = list(dict.fromkeys(curated_sources).keys())
        return curated_sources


@singleton
class PrivateGptUi:
    @inject
    def __init__(
        self,
        ingest_service: IngestService,
        chat_service: ChatService,
        chunks_service: ChunksService,
        summarize_service: SummarizeService,
        memory_service: MemoryService,
    ) -> None:
        self._ingest_service = ingest_service
        self._chat_service = chat_service
        self._chunks_service = chunks_service
        self._summarize_service = summarize_service
        self._memory_service = memory_service

        self._ui_block = None
        self._selected_filename = None

        default_mode_map = {mode.value: mode for mode in Modes}
        self._default_mode = default_mode_map.get(
            settings().ui.default_mode, Modes.RAG_MODE
        )
        self._system_prompt = self._get_default_system_prompt(self._default_mode)

    @staticmethod
    def _get_default_system_prompt(mode: Modes) -> str:
        if mode == Modes.RAG_MODE:
            return settings().ui.default_query_system_prompt
        elif mode == Modes.BASIC_CHAT_MODE:
            return settings().ui.default_chat_system_prompt
        elif mode == Modes.SUMMARIZE_MODE:
            return settings().ui.default_summarization_system_prompt
        return ""

    @staticmethod
    def _get_default_mode_explanation(mode: Modes) -> str:
        if mode == Modes.RAG_MODE:
            return "Get contextualized answers from selected files."
        elif mode == Modes.SEARCH_MODE:
            return "Find relevant chunks of text in selected files."
        elif mode == Modes.BASIC_CHAT_MODE:
            return "Chat with the LLM using its training data. Files are ignored."
        elif mode == Modes.SUMMARIZE_MODE:
            return "Generate a summary of the selected files. Prompt to customize the result."
        return ""

    def _set_system_prompt(self, system_prompt_input: str) -> None:
        logger.info(f"Setting system prompt to: {system_prompt_input}")
        self._system_prompt = system_prompt_input

    def _set_current_mode(self, mode: Modes) -> Any:
        self._system_prompt = self._get_default_system_prompt(mode)
        explanation = self._get_default_mode_explanation(mode)
        interactive = self._system_prompt is not None
        return [
            gr.update(placeholder=self._system_prompt, interactive=interactive),
            gr.update(value=explanation),
        ]

    def _list_ingested_files(self) -> list[list[str]]:
        files = set()
        for doc in self._ingest_service.list_ingested():
            if doc.doc_metadata is None:
                continue
            file_name = doc.doc_metadata.get("file_name", "[FILE NAME MISSING]")
            files.add(file_name)
        return [[row] for row in files]

    def _upload_file(self, files: list[str]) -> None:
        paths = [Path(file) for file in files]
        file_names = [path.name for path in paths]
        doc_ids_to_delete = []
        for doc in self._ingest_service.list_ingested():
            if doc.doc_metadata and doc.doc_metadata["file_name"] in file_names:
                doc_ids_to_delete.append(doc.doc_id)
        for doc_id in doc_ids_to_delete:
            self._ingest_service.delete(doc_id)

        self._ingest_service.bulk_ingest([(str(path.name), path) for path in paths])

    def _delete_all_files(self) -> Any:
        for doc in self._ingest_service.list_ingested():
            self._ingest_service.delete(doc.doc_id)
        return [
            gr.List(self._list_ingested_files()),
            gr.components.Button(interactive=False),
            gr.components.Button(interactive=False),
            gr.components.Textbox("All files"),
        ]

    def _delete_selected_file(self) -> Any:
        for doc in self._ingest_service.list_ingested():
            if doc.doc_metadata and doc.doc_metadata["file_name"] == self._selected_filename:
                self._ingest_service.delete(doc.doc_id)
        return [
            gr.List(self._list_ingested_files()),
            gr.components.Button(interactive=False),
            gr.components.Button(interactive=False),
            gr.components.Textbox("All files"),
        ]

    def _deselect_selected_file(self) -> Any:
        self._selected_filename = None
        return [
            gr.components.Button(interactive=False),
            gr.components.Button(interactive=False),
            gr.components.Textbox("All files"),
        ]

    def _selected_a_file(self, select_data: gr.SelectData) -> Any:
        self._selected_filename = select_data.value
        return [
            gr.components.Button(interactive=True),
            gr.components.Button(interactive=True),
            gr.components.Textbox(self._selected_filename),
        ]

    # --- Dashboard View Renderers ---

    def _render_dashboard_html(self) -> str:
        profile = self._memory_service.get_profile()
        stats = profile.get("stats", {})
        interests = profile.get("interests", [])
        facts = profile.get("learned_facts", [])

        interests_html = "".join(
            f"<span style='display:inline-block; background-color:rgba(199, 186, 255, 0.2); color:#C7BAFF; border:1px solid #C7BAFF; padding:4px 10px; margin:4px; border-radius:12px; font-weight:bold; font-size:12px;'>{interest}</span>"
            for interest in interests
        )
        if not interests_html:
            interests_html = "<span style='color:var(--body-text-color-subdued);'><i>No topics learned yet. Start chatting to build your interest profile.</i></span>"

        facts_html = "".join(
            f"<li style='margin-bottom:8px; font-size:13px; color:var(--body-text-color-subdued); padding: 4px; border-bottom: 1px solid rgba(255,255,255,0.05);'>💡 {fact}</li>"
            for fact in facts
        )
        if not facts_html:
            facts_html = "<span style='color:var(--body-text-color-subdued);'><i>No behavior facts learned yet. Tell the AI how you want it to format or behave!</i></span>"

        html = f"""
        <div style='padding:20px; background-color:var(--block-background-fill); border: 1px solid var(--border-color-primary); border-radius:8px; font-family:inherit;'>
            <h3 style='margin-top:0; color:#C7BAFF; font-size:18px; border-bottom: 2px solid #C7BAFF; padding-bottom: 8px;'>🤖 AI Adaptive Learning Profile</h3>
            
            <div style='display:grid; grid-template-columns: repeat(3, 1fr); gap:16px; margin-top:20px; margin-bottom:20px;'>
                <div style='background-color:rgba(199, 186, 255, 0.05); border:1px solid rgba(199, 186, 255, 0.2); padding:16px; border-radius:6px; text-align:center;'>
                    <div style='font-size:28px; font-weight:bold; color:#C7BAFF;'>{stats.get("total_queries", 0)}</div>
                    <div style='font-size:12px; color:var(--body-text-color-subdued); margin-top:4px;'>Queries Processed</div>
                </div>
                <div style='background-color:rgba(199, 186, 255, 0.05); border:1px solid rgba(199, 186, 255, 0.2); padding:16px; border-radius:6px; text-align:center;'>
                    <div style='font-size:28px; font-weight:bold; color:#C7BAFF;'>{stats.get("total_sessions", 0)}</div>
                    <div style='font-size:12px; color:var(--body-text-color-subdued); margin-top:4px;'>Conversation Sessions</div>
                </div>
                <div style='background-color:rgba(199, 186, 255, 0.05); border:1px solid rgba(199, 186, 255, 0.2); padding:16px; border-radius:6px; text-align:center;'>
                    <div style='font-size:16px; font-weight:bold; color:#C7BAFF; padding: 6px 0;'>{profile.get("explicit_preferences", {}).get("tone", "Adaptive")}</div>
                    <div style='font-size:12px; color:var(--body-text-color-subdued); margin-top:4px;'>Response Tone</div>
                </div>
            </div>
            
            <h4 style='margin-bottom:10px; font-size:15px; color:var(--body-text-color);'>🎯 Learned Areas of Interest</h4>
            <div style='margin-bottom:24px; padding: 10px; background-color: rgba(255,255,255,0.02); border-radius: 6px;'>{interests_html}</div>
            
            <h4 style='margin-bottom:10px; font-size:15px; color:var(--body-text-color);'>🧠 Learned Adaptive Behavior</h4>
            <ul style='margin-top:0; padding-left:0; list-style-type:none;'>{facts_html}</ul>
        </div>
        """
        return html

    def _update_dashboard_view(self) -> Any:
        profile = self._memory_service.get_profile()
        facts = profile.get("learned_facts", [])
        return [
            gr.update(value=self._render_dashboard_html()),
            gr.update(choices=facts, value=facts[0] if facts else None)
        ]

    # --- Session Recall Handlers (Short-Term & Long-Term Recall) ---

    def _get_history_dropdown_choices(self) -> list[str]:
        convs = self._memory_service.list_conversations()
        return [f"{c['title']} ({c['id']})" for c in convs]

    def _handle_select_session(self, select_val: str) -> Any:
        if not select_val:
            return [gr.update(), gr.update(), ""]
        try:
            # Extract UUID from selection format: "title (uuid)"
            sid = select_val.split("(")[-1].strip(")")
            history = self._memory_service.get_conversation(sid)
            
            # Recalculate smart recommendations
            recs = self._memory_service.get_recommendations(history)
            rec_updates = recs + [""] * (3 - len(recs))
            
            return [
                gr.update(value=history),
                sid,
                gr.update(value=rec_updates[0], visible=bool(rec_updates[0])),
                gr.update(value=rec_updates[1], visible=bool(rec_updates[1])),
                gr.update(value=rec_updates[2], visible=bool(rec_updates[2])),
            ]
        except Exception as e:
            logger.error(f"Error loading conversation session: {e}")
            return [gr.update(), gr.update(), gr.update(), gr.update(), gr.update()]

    def _handle_new_session(self) -> Any:
        new_id = str(uuid.uuid4())
        recs = self._memory_service.get_recommendations([])
        rec_updates = recs + [""] * (3 - len(recs))
        return [
            gr.update(value=[]),
            new_id,
            gr.update(value=rec_updates[0], visible=bool(rec_updates[0])),
            gr.update(value=rec_updates[1], visible=bool(rec_updates[1])),
            gr.update(value=rec_updates[2], visible=bool(rec_updates[2])),
            gr.update(value="") # clear textbox
        ]

    def _handle_save_session(self, history: list[list[str]], session_id: str) -> Any:
        if not history:
            return gr.update()
        # Save session
        self._memory_service.save_conversation(session_id, "", history)
        # Update dropdown choices
        choices = self._get_history_dropdown_choices()
        current_selection = choices[0] if choices else ""
        return gr.update(choices=choices, value=current_selection)

    def _handle_delete_session(self, select_val: str) -> Any:
        if not select_val:
            return [gr.update(), gr.update(), gr.update()]
        try:
            sid = select_val.split("(")[-1].strip(")")
            self._memory_service.delete_conversation(sid)
            choices = self._get_history_dropdown_choices()
            new_id = str(uuid.uuid4())
            recs = self._memory_service.get_recommendations([])
            rec_updates = recs + [""] * (3 - len(recs))
            return [
                gr.update(choices=choices, value=None),
                gr.update(value=[]),
                new_id,
                gr.update(value=rec_updates[0], visible=bool(rec_updates[0])),
                gr.update(value=rec_updates[1], visible=bool(rec_updates[1])),
                gr.update(value=rec_updates[2], visible=bool(rec_updates[2])),
            ]
        except Exception as e:
            logger.error(f"Error deleting conversation session: {e}")
            return [gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()]

    # --- Preferences Updates ---

    def _handle_change_theme(self, preset_name: str) -> str:
        profile = self._memory_service.get_profile()
        profile["theme_preset"] = preset_name
        self._memory_service.save_profile(profile)
        style_content = THEME_PRESETS.get(preset_name, THEME_PRESETS["Midnight Aurora"])
        return f"<style id='dynamic-theme-css'>{style_content}</style>"

    def _handle_save_preferences(self, name: str, role: str, tone: str, detail: str, custom_inst: str, theme: str) -> Any:
        self._memory_service.update_user_details(name, role)
        self._memory_service.update_explicit_preferences(tone, detail, custom_inst)
        profile = self._memory_service.get_profile()
        profile["theme_preset"] = theme
        self._memory_service.save_profile(profile)
        
        dashboard_update, facts_update = self._update_dashboard_view()
        style_content = THEME_PRESETS.get(theme, THEME_PRESETS["Midnight Aurora"])
        return [
            dashboard_update,
            facts_update,
            f"<style id='dynamic-theme-css'>{style_content}</style>"
        ]

    def _handle_delete_fact(self, fact: str) -> Any:
        if fact:
            self._memory_service.delete_learned_fact(fact)
        return self._update_dashboard_view()

    def _handle_add_fact(self, fact: str) -> Any:
        if fact:
            self._memory_service.add_learned_fact(fact)
        return [
            gr.update(value=""), # clear text input
            *self._update_dashboard_view()
        ]

    # --- Smart Contextual Recommendations update ---

    def _update_recommendations_after_chat(self, history: list[list[str]]) -> Any:
        recs = self._memory_service.get_recommendations(history)
        rec_updates = recs + [""] * (3 - len(recs))
        return [
            gr.update(value=rec_updates[0], visible=bool(rec_updates[0])),
            gr.update(value=rec_updates[1], visible=bool(rec_updates[1])),
            gr.update(value=rec_updates[2], visible=bool(rec_updates[2])),
        ]

    # --- Developer Workspace Handlers ---

    def _handle_export_chat(self, history: list[list[str]]) -> Any:
        if not history:
            return gr.update(visible=False)
        
        md_content = "# Chat History Export\n\n"
        for user_msg, bot_msg in history:
            if user_msg:
                md_content += f"### 👤 User:\n{user_msg}\n\n"
            if bot_msg:
                bot_clean = bot_msg.split(SOURCES_SEPARATOR)[0]
                md_content += f"### 🤖 Assistant:\n{bot_clean}\n\n"
                if SOURCES_SEPARATOR in bot_msg:
                    sources = bot_msg.split(SOURCES_SEPARATOR)[1]
                    md_content += f"*Sources:*\n{sources}\n\n"
            md_content += "---\n\n"
            
        import tempfile
        temp_dir = Path(PROJECT_ROOT_PATH) / "artifacts"
        temp_dir.mkdir(exist_ok=True)
        export_file_path = temp_dir / "chat_export.md"
        export_file_path.write_text(md_content, encoding="utf-8")
        
        return gr.update(value=str(export_file_path), visible=True)

    def _run_code_interpreter(self, code_str: str) -> str:
        import io
        import sys
        import traceback
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            local_vars = {}
            exec(code_str, {"__builtins__": __builtins__}, local_vars)
            
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            output = stdout_capture.getvalue()
            errors = stderr_capture.getvalue()
            
            res = ""
            if output:
                res += f"--- Execution Output ---\n{output}\n"
            if errors:
                res += f"--- Execution Errors ---\n{errors}\n"
            return res or "Code executed successfully with no output."
        except Exception as e:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            return f"--- Execution Failed ---\n{traceback.format_exc()}"

    def _handle_developer_task(
        self,
        mode: str,
        code_input: str,
        context_input: str
    ) -> Iterable[tuple[str, str]]:
        prompts = {
            "Code Generation": "You are an expert AI code generator. Write clean, well-commented, production-ready code based on the instructions. Provide ONLY code in the first block, then a brief explanation.",
            "Debugging Assistant": "You are an AI debugging assistant. Analyze the provided code and error context. Identify bugs, explain the root causes, and write the corrected code. Provide the corrected code in the code section and explain the fix in the markdown section.",
            "Code Explanation": "You are a senior code reviewer. Walk through the logic, control flow, design patterns, and complexity (Time/Space) of the code. Explain it clearly.",
            "Code Optimization Suggestions": "You are a performance engineer. Profile the provided code, identify bottlenecks (complexity, memory, system calls), suggest optimization techniques, and write the optimized version.",
            "SQL Query Generator": "You are a database administrator and SQL expert. Write a clean SQL query based on the table descriptions or request. Provide ONLY the SQL query in the first block, then explain the logic.",
            "AI API Generator": "You are an API designer. Design a clean REST or GraphQL API (e.g. FastAPI, Express) for the requested capability. Write clean code and explain endpoint contracts.",
            "AI Testing Assistant": "You are a QA automation engineer. Generate comprehensive unit tests (e.g., using pytest, unittest, or jest) covering edge cases, happy paths, and error scenarios for the provided code."
        }
        
        system_prompt = prompts.get(mode, "You are a helpful software engineering assistant.")
        user_message = f"Code Input:\n```\n{code_input}\n```\n\nContext/Requirements:\n{context_input}"
        
        messages = [
            ChatMessage(content=system_prompt, role=MessageRole.SYSTEM),
            ChatMessage(content=user_message, role=MessageRole.USER)
        ]
        
        try:
            query_stream = self._chat_service.stream_chat(
                messages=messages,
                use_context=False,
            )
            
            full_response = ""
            for delta in query_stream.response:
                if isinstance(delta, str):
                    full_response += delta
                elif hasattr(delta, "delta"):
                    full_response += delta.delta or ""
                
                code_output = ""
                explanation_output = ""
                
                if "```" in full_response:
                    parts = full_response.split("```")
                    for i, part in enumerate(parts):
                        if i % 2 == 1:
                            lines = part.split("\n")
                            if lines and (lines[0].strip() in ["python", "js", "sql", "html", "css", "cpp", "c", "bash", "json", "yaml"]):
                                code_output += "\n".join(lines[1:])
                            else:
                                code_output += part
                        else:
                            explanation_output += part
                else:
                    explanation_output = full_response
                
                yield code_output.strip(), explanation_output.strip()
        except Exception as e:
            logger.error(f"Error in developer assistant task: {e}")
            yield "", f"Error processing task: {str(e)}"

    # --- Custom Chat Stream Generation Engine ---

    def _chat_custom(
        self,
        history: list[list[str]],
        session_id: str,
        mode: Modes,
        system_prompt: str | None,
        last_user_message: str
    ) -> Iterable[list[list[str]]]:
        if not history:
            yield []
            return

        # 1. Trigger AI adaptive learning & preference updates
        self._memory_service.learn_from_interaction(last_user_message, "")

        # Yield visual thinking animation state immediately
        history[-1][1] = "<span class='thinking-dots'>🧠 AI is thinking<span class='dot'>.</span><span class='dot'>.</span><span class='dot'>.</span></span>"
        yield history

        # Clear the thinking indicator before streaming response tokens
        history[-1][1] = ""

        # 2. Compile adaptive personalized system prompt
        base_prompt = system_prompt or self._system_prompt
        adaptive_prompt = self._memory_service.compile_adaptive_prompt(base_prompt)

        # 3. Build chat history message list
        all_messages: list[ChatMessage] = []
        # Add past context up to 20 messages
        for interaction in history[:-1]:
            all_messages.append(ChatMessage(content=interaction[0], role=MessageRole.USER))
            if len(interaction) > 1 and interaction[1] is not None:
                all_messages.append(
                    ChatMessage(
                        content=interaction[1].split(SOURCES_SEPARATOR)[0],
                        role=MessageRole.ASSISTANT
                    )
                )

        # Append last prompt
        all_messages.append(ChatMessage(content=last_user_message, role=MessageRole.USER))

        # Prep system message if prompt active
        if adaptive_prompt:
            all_messages.insert(0, ChatMessage(content=adaptive_prompt, role=MessageRole.SYSTEM))

        # Retrieve selected file context filter
        context_filter = None
        if self._selected_filename is not None:
            docs_ids = []
            for ingested in self._ingest_service.list_ingested():
                if ingested.doc_metadata and ingested.doc_metadata["file_name"] == self._selected_filename:
                    docs_ids.append(ingested.doc_id)
            context_filter = ContextFilter(docs_ids=docs_ids)

        use_context = (mode == Modes.RAG_MODE)

        # Process standard chat streams
        if mode == Modes.RAG_MODE or mode == Modes.BASIC_CHAT_MODE:
            try:
                query_stream = self._chat_service.stream_chat(
                    messages=all_messages,
                    use_context=use_context,
                    context_filter=context_filter,
                )
                history[-1][1] = ""
                for delta in query_stream.response:
                    if isinstance(delta, str):
                        history[-1][1] += str(delta)
                    elif isinstance(delta, ChatResponse):
                        history[-1][1] += delta.delta or ""
                    yield history
                    time.sleep(0.01)

                # Render sources
                if query_stream.sources:
                    sources_text = SOURCES_SEPARATOR + "\n"
                    cur_sources = Source.curate_sources(query_stream.sources)
                    used_files = set()
                    for index, source in enumerate(cur_sources, start=1):
                        if f"{source.file}-{source.page}" not in used_files:
                            sources_text += f"{index}. {source.file} (page {source.page}) \n\n"
                            used_files.add(f"{source.file}-{source.page}")
                    history[-1][1] += sources_text
                    yield history
            except Exception as e:
                history[-1][1] = f"Error generating response: {e}"
                yield history
        elif mode == Modes.SEARCH_MODE:
            try:
                response = self._chunks_service.retrieve_relevant(
                    text=last_user_message, limit=4, prev_next_chunks=0
                )
                sources = Source.curate_sources(response)
                history[-1][1] = "\n\n\n".join(
                    f"{index}. **{source.file} (page {source.page})**\n {source.text}"
                    for index, source in enumerate(sources, start=1)
                )
                yield history
            except Exception as e:
                history[-1][1] = f"Error performing search: {e}"
                yield history
        elif mode == Modes.SUMMARIZE_MODE:
            try:
                summary_stream = self._summarize_service.stream_summarize(
                    use_context=True,
                    context_filter=context_filter,
                    instructions=last_user_message,
                )
                history[-1][1] = ""
                for token in summary_stream:
                    history[-1][1] += str(token)
                    yield history
            except Exception as e:
                history[-1][1] = f"Error generating summary: {e}"
                yield history

        # 4. Autosave current conversation interaction
        self._memory_service.save_conversation(session_id, "", history)

    def _clear_chat_session(self, session_id: str) -> Any:
        new_id = str(uuid.uuid4())
        recs = self._memory_service.get_recommendations([])
        rec_updates = recs + [""] * (3 - len(recs))
        return [
            [], # Clear chatbot
            "", # Clear message
            new_id,
            gr.update(value=rec_updates[0], visible=bool(rec_updates[0])),
            gr.update(value=rec_updates[1], visible=bool(rec_updates[1])),
            gr.update(value=rec_updates[2], visible=bool(rec_updates[2])),
        ]

    # --- UI Layout Builder ---

    def _build_ui_blocks(self) -> gr.Blocks:
        logger.debug("Creating the UI blocks")
        with gr.Blocks(
            title=UI_TAB_TITLE,
            theme=gr.themes.Soft(primary_hue=slate),
            css=".logo { "
            "display:flex;"
            "background-color: #C7BAFF;"
            "height: 80px;"
            "border-radius: 8px;"
            "align-content: center;"
            "justify-content: center;"
            "align-items: center;"
            "}"
            ".logo img { height: 25% }"
            ".contain { display: flex !important; flex-direction: column !important; }"
            "#chatbot { flex-grow: 1 !important; overflow: auto !important; height: 520px !important; scroll-behavior: smooth !important; }"
            "hr { margin-top: 1em; margin-bottom: 1em; border: 0; border-top: 1px solid #FFF; }"
            ".avatar-image { background-color: antiquewhite; border-radius: 2px; }"
            "footer { display: none !important; }"
            "/* Message slide-in transitions */"
            "#chatbot .message { animation: fadeInSlide 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards !important; }"
            "@keyframes fadeInSlide { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }"
            "/* Code block styling */"
            "#chatbot pre { background: rgba(0,0,0,0.5) !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 8px !important; padding: 12px !important; font-family: monospace !important; box-shadow: inset 0 0 10px rgba(0,0,0,0.8) !important; }"
            "#chatbot code { color: #00ffcc !important; }"
            "/* Floating AI assistant pulse animation */"
            "@keyframes floatPulse { 0% { transform: scale(1); box-shadow: 0 0 15px rgba(255, 0, 127, 0.5); } 50% { transform: scale(1.08); box-shadow: 0 0 25px rgba(0, 255, 204, 0.8); } 100% { transform: scale(1); box-shadow: 0 0 15px rgba(255, 0, 127, 0.5); } }"
            "/* Custom thinking dots animation */"
            ".thinking-dots { display: inline-flex; align-items: center; color: #ff007f; font-weight: bold; animation: pulse 1.5s infinite; }"
            ".thinking-dots .dot { animation: dotDelay 1.5s infinite; }"
            ".thinking-dots .dot:nth-child(2) { animation-delay: 0.2s; }"
            ".thinking-dots .dot:nth-child(3) { animation-delay: 0.4s; }"
            "@keyframes dotDelay { 0%, 100% { opacity: 0.2; } 50% { opacity: 1; } }",
            js="""
            () => {
                // Auto-scroll chat observer
                setTimeout(() => {
                    const target = document.querySelector('#chatbot');
                    if (target) {
                        const observer = new MutationObserver(() => {
                            const container = target.querySelector('.contain');
                            if (container) {
                                container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
                            }
                        });
                        observer.observe(target, { childList: true, subtree: true });
                    }
                }, 1000);
            }
            """
        ) as blocks:
            
            # Application State
            session_id_state = gr.State(value=str(uuid.uuid4()))
            current_prompt_state = gr.State(value="")

            # Dynamic Theme Style Element
            profile = self._memory_service.get_profile()
            active_theme = profile.get("theme_preset", "Midnight Aurora")
            initial_css = THEME_PRESETS.get(active_theme, THEME_PRESETS["Midnight Aurora"])
            dynamic_style = gr.HTML(value=f"<style id='dynamic-theme-css'>{initial_css}</style>", visible=False)

            with gr.Row():
                gr.HTML(f"<div class='logo'/><img src={logo_svg} alt=PrivateGPT></div")

            with gr.Row(equal_height=False):
                # Left Sidebar Panel
                with gr.Column(scale=3):
                    # Active Profile Card
                    profile = self._memory_service.get_profile()
                    with gr.Accordion("📂 Saved Conversation Sessions", open=True):
                        choices = self._get_history_dropdown_choices()
                        history_dropdown = gr.Dropdown(
                            choices=choices,
                            value=None,
                            label="Recall Previous Chat",
                            interactive=True,
                            allow_custom_value=False
                        )
                        save_btn = gr.Button("💾 Save Current Session", size="sm")
                        delete_session_btn = gr.Button("🗑️ Delete Selected Session", size="sm")

                    default_mode = self._default_mode
                    mode = gr.Radio(
                        [mode.value for mode in MODES],
                        label="Mode",
                        value=default_mode,
                    )
                    explanation_mode = gr.Textbox(
                        placeholder=self._get_default_mode_explanation(default_mode),
                        show_label=False,
                        max_lines=3,
                        interactive=False,
                    )
                    upload_button = gr.components.UploadButton(
                        "Upload File(s)",
                        type="filepath",
                        file_count="multiple",
                        size="sm",
                    )
                    ingested_dataset = gr.List(
                        self._list_ingested_files,
                        headers=["File name"],
                        label="Ingested Files",
                        height=235,
                        interactive=False,
                        render=False,
                    )
                    upload_button.upload(
                        self._upload_file,
                        inputs=upload_button,
                        outputs=ingested_dataset,
                    )
                    ingested_dataset.change(
                        self._list_ingested_files,
                        outputs=ingested_dataset,
                    )
                    ingested_dataset.render()
                    
                    deselect_file_button = gr.components.Button(
                        "De-select selected file", size="sm", interactive=False
                    )
                    selected_text = gr.components.Textbox(
                        "All files", label="Selected for Query or Deletion", max_lines=1
                    )
                    delete_file_button = gr.components.Button(
                        "🗑️ Delete selected file",
                        size="sm",
                        visible=settings().ui.delete_file_button_enabled,
                        interactive=False,
                    )
                    delete_files_button = gr.components.Button(
                        "⚠️ Delete ALL files",
                        size="sm",
                        visible=settings().ui.delete_all_files_button_enabled,
                    )
                    
                    deselect_file_button.click(
                        self._deselect_selected_file,
                        outputs=[delete_file_button, deselect_file_button, selected_text],
                    )
                    ingested_dataset.select(
                        fn=self._selected_a_file,
                        outputs=[delete_file_button, deselect_file_button, selected_text],
                    )
                    delete_file_button.click(
                        self._delete_selected_file,
                        outputs=[ingested_dataset, delete_file_button, deselect_file_button, selected_text],
                    )
                    delete_files_button.click(
                        self._delete_all_files,
                        outputs=[ingested_dataset, delete_file_button, deselect_file_button, selected_text],
                    )
                    
                    system_prompt_input = gr.Textbox(
                        placeholder=self._system_prompt,
                        label="System Prompt Override",
                        lines=2,
                        interactive=True,
                        render=False,
                    )
                    mode.change(
                        self._set_current_mode,
                        inputs=mode,
                        outputs=[system_prompt_input, explanation_mode],
                    )
                    system_prompt_input.blur(
                        self._set_system_prompt,
                        inputs=system_prompt_input,
                    )

                    def get_model_label() -> str | None:
                        config_settings = settings()
                        if config_settings is None:
                            raise ValueError("Settings are not configured.")
                        llm_mode = config_settings.llm.mode
                        model_mapping = {
                            "llamacpp": config_settings.llamacpp.llm_hf_model_file,
                            "openai": config_settings.openai.model,
                            "openailike": config_settings.openai.model,
                            "azopenai": config_settings.azopenai.llm_model,
                            "sagemaker": config_settings.sagemaker.llm_endpoint_name,
                            "mock": llm_mode,
                            "ollama": config_settings.ollama.llm_model,
                            "gemini": config_settings.gemini.model,
                        }
                        if llm_mode not in model_mapping:
                            return None
                        return model_mapping[llm_mode]

                # Main Tabs Panel
                with gr.Column(scale=7, elem_id="col"):
                    model_label = get_model_label()
                    label_text = f"LLM: {settings().llm.mode}" + (f" | Model: {model_label}" if model_label else "")

                    with gr.Tabs() as main_tabs:
                        # 1. Chat Room Tab
                        with gr.Tab("💬 RAG Chat Room", id="chat_room_tab"):
                            chatbot = gr.Chatbot(
                                label=label_text,
                                show_copy_button=True,
                                elem_id="chatbot",
                                avatar_images=(None, AVATAR_BOT),
                            )
                            with gr.Row():
                                msg = gr.Textbox(
                                    placeholder="Type a message...",
                                    show_label=False,
                                    scale=8,
                                )
                                submit_btn = gr.Button("Submit", variant="primary", scale=1)
                                clear_btn = gr.Button("Clear", scale=1)
                            
                            # Smart Recommendation buttons
                            recs = self._memory_service.get_recommendations([])
                            rec_vals = recs + [""] * (3 - len(recs))
                            with gr.Row():
                                gr.HTML("<div style='font-size:12px; color:var(--body-text-color-subdued); padding: 4px 0;'>💡 Recommended questions:</div>")
                            with gr.Row():
                                rec_btn1 = gr.Button(rec_vals[0], size="sm", visible=bool(rec_vals[0]))
                                rec_btn2 = gr.Button(rec_vals[1], size="sm", visible=bool(rec_vals[1]))
                                rec_btn3 = gr.Button(rec_vals[2], size="sm", visible=bool(rec_vals[2]))
                            
                            # Chat Export Controls
                            with gr.Row():
                                export_chat_btn = gr.Button("📤 Export Chat History", size="sm")
                                export_file = gr.File(label="Download Exported Markdown", visible=False)

                        # 2. Personalized Dashboard Tab
                        with gr.Tab("📊 Personalized Dashboard", id="dashboard_tab"):
                            dashboard_html = gr.HTML(self._render_dashboard_html())
                            refresh_dashboard_btn = gr.Button("🔄 Refresh Dashboard Statistics", size="sm")

                        # 3. Memory & Custom Preferences Settings Tab
                        with gr.Tab("🧠 Memory & Personalization Settings", id="personalization_tab"):
                            gr.Markdown("### Edit User Profile & Personalization")
                            with gr.Row():
                                user_name_input = gr.Textbox(value=profile.get("user_name", "User"), label="Your Name")
                                user_role_input = gr.Textbox(value=profile.get("role", "Researcher"), label="Your Role / Occupation")
                            
                            with gr.Row():
                                pref_tone = gr.Dropdown(
                                    choices=["Adaptive", "Professional", "Creative", "Concise", "Detailed"],
                                    value=profile.get("explicit_preferences", {}).get("tone", "Adaptive"),
                                    label="Response Style (Tone)"
                                )
                                pref_detail = gr.Dropdown(
                                    choices=["Medium", "Concise", "Detailed"],
                                    value=profile.get("explicit_preferences", {}).get("detail_level", "Medium"),
                                    label="Detail Level"
                                )
                                pref_theme = gr.Dropdown(
                                    choices=list(THEME_PRESETS.keys()),
                                    value=profile.get("theme_preset", "Midnight Aurora"),
                                    label="UI Theme Preset Style"
                                )
                            
                            pref_instructions = gr.Textbox(
                                value=profile.get("explicit_preferences", {}).get("custom_instructions", ""),
                                label="Custom User Instructions (appended to system prompt)",
                                lines=3,
                                placeholder="Example: Always provide source snippets first, then summarize."
                            )
                            save_prefs_btn = gr.Button("💾 Save Personalization Settings", variant="primary")
                            
                            gr.Markdown("---")
                            gr.Markdown("### Manage AI Learned Facts (Long-Term Memory)")
                            facts = profile.get("learned_facts", [])
                            facts_dropdown = gr.Dropdown(
                                choices=facts,
                                value=facts[0] if facts else None,
                                label="Currently Learned Preferences & Facts",
                                interactive=True
                            )
                            with gr.Row():
                                delete_fact_btn = gr.Button("🗑️ Delete Selected Fact", size="sm")
                                refresh_facts_btn = gr.Button("🔄 Refresh List", size="sm")
                            
                            gr.Markdown("#### Manually Add Long-Term Fact:")
                            new_fact_input = gr.Textbox(label="New Fact Description", placeholder="Example: User prefers mathematical formulas in LaTeX.")
                            add_fact_btn = gr.Button("➕ Add Fact", size="sm")

                        # 4. Developer Hub Tab
                        with gr.Tab("💻 Developer Hub", id="developer_hub_tab"):
                            gr.Markdown("## 💻 AI Developer Workbench")
                            with gr.Row():
                                with gr.Column(scale=1):
                                    dev_mode = gr.Dropdown(
                                        choices=[
                                            "Code Generation",
                                            "Debugging Assistant",
                                            "Code Explanation",
                                            "Code Optimization Suggestions",
                                            "SQL Query Generator",
                                            "AI API Generator",
                                            "AI Testing Assistant"
                                        ],
                                        value="Code Generation",
                                        label="Select Developer Tool Mode"
                                    )
                                    dev_code_input = gr.Code(
                                        label="Enter Code or Table Schema here",
                                        language="python",
                                        lines=12,
                                    )
                                    dev_context_input = gr.Textbox(
                                        label="Enter Instructions, Prompt or Error Logs here",
                                        lines=4,
                                        placeholder="Example: Optimize this function for O(N) time / Paste traceback here."
                                    )
                                    process_dev_btn = gr.Button("🚀 Process Developer Task", variant="primary")
                                
                                with gr.Column(scale=1):
                                    dev_code_output = gr.Code(
                                        label="Generated / Optimized Code Result",
                                        language="python",
                                        lines=15,
                                        interactive=False
                                    )
                                    dev_explanation_output = gr.Markdown()
                            
                            gr.Markdown("---")
                            gr.Markdown("### 🎛️ AI Code Interpreter (Sandboxed Python Runner)")
                            with gr.Row():
                                with gr.Column(scale=1):
                                    interpreter_input = gr.Code(
                                        value='def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)\n\nprint("Fibonacci result:", fib(10))',
                                        label="Write Python Code here to Execute",
                                        language="python",
                                        lines=8
                                    )
                                with gr.Column(scale=1):
                                    interpreter_output = gr.Textbox(
                                        label="Console Output / Stderr Traceback",
                                        lines=10,
                                        interactive=False
                                    )
                            run_interpreter_btn = gr.Button("▶️ Run Python Script", variant="primary")

            # --- Bind Event Handlers ---
            
            # Chat flow handling logic
            def user_input_handler(text, history):
                return "", history + [[text, None]], text

            # Regular text submission flow
            submit_event = submit_btn.click(
                fn=user_input_handler,
                inputs=[msg, chatbot],
                outputs=[msg, chatbot, current_prompt_state]
            ).then(
                fn=self._chat_custom,
                inputs=[chatbot, session_id_state, mode, system_prompt_input, current_prompt_state],
                outputs=[chatbot]
            ).then(
                fn=self._update_recommendations_after_chat,
                inputs=[chatbot],
                outputs=[rec_btn1, rec_btn2, rec_btn3]
            ).then(
                fn=self._update_dashboard_view,
                outputs=[dashboard_html, facts_dropdown]
            )

            msg.submit(
                fn=user_input_handler,
                inputs=[msg, chatbot],
                outputs=[msg, chatbot, current_prompt_state]
            ).then(
                fn=self._chat_custom,
                inputs=[chatbot, session_id_state, mode, system_prompt_input, current_prompt_state],
                outputs=[chatbot]
            ).then(
                fn=self._update_recommendations_after_chat,
                inputs=[chatbot],
                outputs=[rec_btn1, rec_btn2, rec_btn3]
            ).then(
                fn=self._update_dashboard_view,
                outputs=[dashboard_html, facts_dropdown]
            )

            # Recommendations Click handlers
            def rec_click_handler(rec_val, history):
                return "", history + [[rec_val, None]], rec_val

            rec_btn1.click(
                fn=rec_click_handler,
                inputs=[rec_btn1, chatbot],
                outputs=[msg, chatbot, current_prompt_state]
            ).then(
                fn=self._chat_custom,
                inputs=[chatbot, session_id_state, mode, system_prompt_input, current_prompt_state],
                outputs=[chatbot]
            ).then(
                fn=self._update_recommendations_after_chat,
                inputs=[chatbot],
                outputs=[rec_btn1, rec_btn2, rec_btn3]
            ).then(
                fn=self._update_dashboard_view,
                outputs=[dashboard_html, facts_dropdown]
            )

            rec_btn2.click(
                fn=rec_click_handler,
                inputs=[rec_btn2, chatbot],
                outputs=[msg, chatbot, current_prompt_state]
            ).then(
                fn=self._chat_custom,
                inputs=[chatbot, session_id_state, mode, system_prompt_input, current_prompt_state],
                outputs=[chatbot]
            ).then(
                fn=self._update_recommendations_after_chat,
                inputs=[chatbot],
                outputs=[rec_btn1, rec_btn2, rec_btn3]
            ).then(
                fn=self._update_dashboard_view,
                outputs=[dashboard_html, facts_dropdown]
            )

            rec_btn3.click(
                fn=rec_click_handler,
                inputs=[rec_btn3, chatbot],
                outputs=[msg, chatbot, current_prompt_state]
            ).then(
                fn=self._chat_custom,
                inputs=[chatbot, session_id_state, mode, system_prompt_input, current_prompt_state],
                outputs=[chatbot]
            ).then(
                fn=self._update_recommendations_after_chat,
                inputs=[chatbot],
                outputs=[rec_btn1, rec_btn2, rec_btn3]
            ).then(
                fn=self._update_dashboard_view,
                outputs=[dashboard_html, facts_dropdown]
            )

            # Clear session
            clear_btn.click(
                fn=self._clear_chat_session,
                inputs=[session_id_state],
                outputs=[chatbot, msg, session_id_state, rec_btn1, rec_btn2, rec_btn3]
            )

            # Previous sessions Recall & Save handlers
            history_dropdown.select(
                fn=self._handle_select_session,
                inputs=[history_dropdown],
                outputs=[chatbot, session_id_state, rec_btn1, rec_btn2, rec_btn3]
            )
            save_btn.click(
                fn=self._handle_save_session,
                inputs=[chatbot, session_id_state],
                outputs=[history_dropdown]
            )
            delete_session_btn.click(
                fn=self._handle_delete_session,
                inputs=[history_dropdown],
                outputs=[history_dropdown, chatbot, session_id_state, rec_btn1, rec_btn2, rec_btn3]
            )

            # Refresh Dashboard Stats
            refresh_dashboard_btn.click(
                fn=self._update_dashboard_view,
                outputs=[dashboard_html, facts_dropdown]
            )

            # Save explicit preferences
            save_prefs_btn.click(
                fn=self._handle_save_preferences,
                inputs=[user_name_input, user_role_input, pref_tone, pref_detail, pref_instructions, pref_theme],
                outputs=[dashboard_html, facts_dropdown, dynamic_style]
            )

            # Instant Theme Changer Preset Dropdown
            pref_theme.change(
                fn=self._handle_change_theme,
                inputs=[pref_theme],
                outputs=[dynamic_style]
            )

            # Manual Memory Fact Add / Delete handlers
            delete_fact_btn.click(
                fn=self._handle_delete_fact,
                inputs=[facts_dropdown],
                outputs=[dashboard_html, facts_dropdown]
            )
            refresh_facts_btn.click(
                fn=self._update_dashboard_view,
                outputs=[dashboard_html, facts_dropdown]
            )
            add_fact_btn.click(
                fn=self._handle_add_fact,
                inputs=[new_fact_input],
                outputs=[new_fact_input, dashboard_html, facts_dropdown]
            )

            # Developer Workspace Event Bindings
            process_dev_btn.click(
                fn=self._handle_developer_task,
                inputs=[dev_mode, dev_code_input, dev_context_input],
                outputs=[dev_code_output, dev_explanation_output]
            )

            run_interpreter_btn.click(
                fn=self._run_code_interpreter,
                inputs=[interpreter_input],
                outputs=[interpreter_output]
            )

            # Export chat handler click binding
            export_chat_btn.click(
                fn=self._handle_export_chat,
                inputs=[chatbot],
                outputs=[export_file]
            )

            # Floating AI Assistant widget
            gr.HTML(
                "<div id='floating-assistant' onclick=\"document.querySelector('#chatbot').scrollIntoView({behavior: 'smooth'})\" style='position:fixed; bottom:25px; right:25px; z-index:9999; width:55px; height:55px; border-radius:50%; background:linear-gradient(135deg, #ff007f, #00ffcc); display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 0 15px rgba(255, 0, 127, 0.5); animation: floatPulse 2s infinite;'>"
                "  <span style='font-size:26px;'>🧠</span>"
                "</div>"
            )

        return blocks

    def get_ui_blocks(self) -> gr.Blocks:
        if self._ui_block is None:
            self._ui_block = self._build_ui_blocks()
        return self._ui_block

    def mount_in_app(self, app: FastAPI, path: str) -> None:
        blocks = self.get_ui_blocks()
        blocks.queue()
        logger.info("Mounting the gradio UI, at path=%s", path)
        gr.mount_gradio_app(app, blocks, path=path, favicon_path=AVATAR_BOT)


if __name__ == "__main__":
    ui = global_injector.get(PrivateGptUi)
    _blocks = ui.get_ui_blocks()
    _blocks.queue()
    _blocks.launch(debug=False, show_api=False)
