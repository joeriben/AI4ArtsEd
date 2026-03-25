"""
Tool Registry for Trashy Chat — On-demand knowledge lookup.

Extensible registry pattern: tools are registered at startup, available to
the chat endpoint's tool-call loop. Compatible with the agentic architecture
(docs/plans/agentic/MASTERPLAN.md) — future phases add tools via register().

Architecture:
    ToolRegistry (singleton)
      └── lookup_reference      (Phase 0: platform knowledge)
      └── lookup_interception   (Phase 0: interception config knowledge)
      └── (future) get_experience_summary  (Phase 1)
      └── (future) check_model_availability (Phase 1)
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section parser — loads trashy_interface_reference.txt into sections
# ---------------------------------------------------------------------------

# Section ID mapping: human-readable keys for the enum
_SECTION_IDS = {
    "1": "platform_overview",
    "2": "platform_structure",
    "3": "text_mode",
    "3b": "canvas_mode",
    "4": "circularity",
    "5": "was_wie_principle",
    "6": "experimental_workflows",
    "7": "lora_training",
    "8": "safety_levels",
    "9": "data_privacy",
    "10": "faq",
    "11": "interface_elements",
    "12": "tips",
    "13": "configurations",
    "14": "troubleshooting",
    "15": "prompt_quality",
    "16": "edutainment",
    "17": "prompt_collapse",
    "18": "platform_news",
}

_SECTION_PATTERN = re.compile(r"^SECTION\s+(\d+b?)\s*:", re.IGNORECASE)
_SEPARATOR = "=" * 80


def _parse_sections(filepath: Path) -> Dict[str, str]:
    """Parse trashy_interface_reference.txt into {section_id: content}."""
    sections: Dict[str, str] = {}

    if not filepath.exists():
        logger.warning(f"[TOOL-REGISTRY] Reference file not found: {filepath}")
        return sections

    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()

    current_id: Optional[str] = None
    current_lines: List[str] = []

    for line in lines:
        match = _SECTION_PATTERN.match(line)
        if match:
            # Save previous section
            if current_id is not None:
                sections[current_id] = "\n".join(current_lines).strip()
            # Start new section
            section_num = match.group(1)
            current_id = _SECTION_IDS.get(section_num)
            current_lines = [line]  # include the header
            if current_id is None:
                logger.warning(f"[TOOL-REGISTRY] Unknown section number: {section_num}")
                current_id = f"section_{section_num}"
        elif line.startswith("END OF KNOWLEDGE BASE"):
            break
        elif line == _SEPARATOR:
            # Skip separator lines
            continue
        elif current_id is not None:
            current_lines.append(line)

    # Save last section
    if current_id is not None:
        sections[current_id] = "\n".join(current_lines).strip()

    logger.info(f"[TOOL-REGISTRY] Parsed {len(sections)} sections from reference file")
    return sections


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """Registry of tools available to chat models."""

    def __init__(self):
        self._tools: Dict[str, dict] = {}  # name -> {"schema": dict, "handler": Callable}

    def register(self, name: str, description: str, parameters: dict, handler: Callable[[dict], str]):
        """Register a tool.

        Args:
            name: Tool name (must be unique).
            description: Human-readable description for the LLM.
            parameters: JSON Schema for the tool's parameters.
            handler: Function(arguments: dict) -> str.
        """
        self._tools[name] = {
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            "handler": handler,
        }
        logger.info(f"[TOOL-REGISTRY] Registered tool: {name}")

    def get_openai_format(self) -> List[dict]:
        """Return tool definitions in OpenAI tools format."""
        return [t["schema"] for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        """Execute a tool by name. Returns result string or error message."""
        tool = self._tools.get(name)
        if not tool:
            logger.warning(f"[TOOL-REGISTRY] Unknown tool: {name}")
            return f"Error: Unknown tool '{name}'"
        try:
            result = tool["handler"](arguments)
            logger.info(f"[TOOL-REGISTRY] Executed {name}: {len(result)} chars")
            return result
        except Exception as e:
            logger.error(f"[TOOL-REGISTRY] Tool {name} failed: {e}")
            return f"Error executing {name}: {e}"

    def list_names(self) -> List[str]:
        return list(self._tools.keys())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get singleton ToolRegistry. Registers built-in tools on first call."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_builtin_tools(_registry)
    return _registry


# ---------------------------------------------------------------------------
# Built-in tools
# ---------------------------------------------------------------------------

def _register_builtin_tools(registry: ToolRegistry):
    """Register all built-in tools."""

    # --- lookup_reference ---
    reference_path = Path(__file__).parent.parent.parent / "trashy_interface_reference.txt"
    sections = _parse_sections(reference_path)
    section_ids = sorted(sections.keys())

    def lookup_reference(args: dict) -> str:
        section = args.get("section", "")
        content = sections.get(section)
        if content is None:
            return f"Section '{section}' not found. Available: {', '.join(section_ids)}"
        return content

    registry.register(
        name="lookup_reference",
        description=(
            "Look up a section from the AI4ArtsEd platform knowledge base. "
            "Use this when users ask about platform features, workflows, configurations, "
            "troubleshooting, or interface elements. Call multiple times for multiple sections."
        ),
        parameters={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "enum": section_ids,
                    "description": "Section to look up. Each covers a specific topic area.",
                },
            },
            "required": ["section"],
        },
        handler=lookup_reference,
    )

    # --- lookup_interception ---
    configs_dir = Path(__file__).parent.parent.parent / "schemas" / "configs" / "interception"

    def lookup_interception(args: dict) -> str:
        action = args.get("action", "")

        if action == "list_configs":
            return _list_interception_configs(configs_dir)
        elif action == "get_config":
            config_id = args.get("config_id", "")
            if not config_id:
                return "Error: 'config_id' is required for 'get_config' action."
            return _get_interception_config(configs_dir, config_id)
        elif action == "get_instruction_templates":
            return _get_instruction_templates()
        else:
            return f"Unknown action '{action}'. Use: list_configs, get_config, get_instruction_templates."

    registry.register(
        name="lookup_interception",
        description=(
            "Look up how the platform's creative transformations (interception configs) work. "
            "Use this when users ask what a specific mode does (e.g., 'What does Bauhaus mode do?'), "
            "how prompt transformation works, or what transformation rules are applied. "
            "Actions: 'list_configs' lists all available configs, 'get_config' shows a specific "
            "config's transformation rules, 'get_instruction_templates' shows the general instruction types."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_configs", "get_config", "get_instruction_templates"],
                    "description": (
                        "Action to perform: 'list_configs' = list all interception configs, "
                        "'get_config' = get a specific config's details (requires config_id), "
                        "'get_instruction_templates' = show the general instruction templates."
                    ),
                },
                "config_id": {
                    "type": "string",
                    "description": (
                        "Config ID (filename without .json) — required for 'get_config'. "
                        "Example: 'bauhaus', 'surrealizer', 'jugendsprache'."
                    ),
                },
            },
            "required": ["action"],
        },
        handler=lookup_interception,
    )


# ---------------------------------------------------------------------------
# Interception tool helpers
# ---------------------------------------------------------------------------

def _list_interception_configs(configs_dir: Path) -> str:
    """List all active interception configs with summary info."""
    if not configs_dir.exists():
        return "Error: Interception configs directory not found."

    entries = []
    for f in sorted(configs_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            name_en = data.get("name", {}).get("en", f.stem)
            desc_en = data.get("description", {}).get("en", "")
            cat_en = data.get("category", {}).get("en", "")
            entries.append(f"- {f.stem}: {name_en} ({cat_en}) — {desc_en}")
        except Exception:
            continue

    if not entries:
        return "No interception configs found."
    return f"Available interception configs ({len(entries)}):\n\n" + "\n".join(entries)


def _get_interception_config(configs_dir: Path, config_id: str) -> str:
    """Get detailed info about a specific interception config."""
    config_path = configs_dir / f"{config_id}.json"
    if not config_path.exists():
        # Check for deactivated/deprecated variants
        for suffix in [".json.deactivated", ".json.deprecated"]:
            alt = configs_dir / f"{config_id}{suffix}"
            if alt.exists():
                return f"Config '{config_id}' exists but is currently deactivated/deprecated."
        available = [f.stem for f in sorted(configs_dir.glob("*.json"))]
        return f"Config '{config_id}' not found. Available: {', '.join(available)}"

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Error reading config '{config_id}': {e}"

    parts = []
    parts.append(f"Config: {config_id}")
    parts.append(f"Name: {data.get('name', {}).get('en', 'N/A')}")
    parts.append(f"Description: {data.get('description', {}).get('en', 'N/A')}")
    parts.append(f"Category: {data.get('category', {}).get('en', 'N/A')}")
    parts.append(f"Pipeline: {data.get('pipeline', 'N/A')}")
    parts.append(f"Instruction type: {data.get('instruction_type', 'N/A')}")

    props = data.get("properties", [])
    if props:
        parts.append(f"Properties: {', '.join(props)}")

    media = data.get("media_preferences", {})
    if media:
        default_out = media.get("default_output", "")
        supported = media.get("supported_types", [])
        parts.append(f"Media: default={default_out}, supported={', '.join(supported)}")

    # The pedagogical transformation context (the core content)
    context = data.get("context", {})
    if context:
        context_en = context.get("en", "")
        if context_en:
            parts.append(f"\nTransformation rules (English):\n{context_en}")
    else:
        # Some configs use chunks directly instead of context
        chunks = data.get("chunks", [])
        if chunks:
            parts.append(f"\nThis config uses {len(chunks)} pipeline chunk(s) instead of a direct context.")

    return "\n".join(parts)


def _get_instruction_templates() -> str:
    """Return instruction templates from instruction_selector (no safety prefixes)."""
    # Import here to avoid circular imports at module level
    try:
        import sys
        engine_path = Path(__file__).parent.parent.parent / "schemas" / "engine"
        if str(engine_path) not in sys.path:
            sys.path.insert(0, str(engine_path))
        from instruction_selector import INSTRUCTION_TYPES
    except ImportError:
        return "Error: Could not load instruction templates."

    parts = ["Instruction templates used by the interception system:\n"]
    for name, info in INSTRUCTION_TYPES.items():
        desc = info.get("description", "")
        default = info.get("default")
        parts.append(f"--- {name} ---")
        parts.append(f"Description: {desc}")
        if default:
            parts.append(f"Template:\n{default}")
        else:
            parts.append("(Alias — redirects to another type)")
        parts.append("")

    return "\n".join(parts)
