"""One answer of a local model, as a ComfyUI node.

The DevServer's local LLM backend (my_app/services/llm_client.py) queues a
prompt of this one node for every chat, safety check and image reading it
runs locally; the answer comes back through /history as the node's ui output,
and the pieces are published on the websocket while they are written
(ai4artsed.llm.token). In a workflow built in ComfyUI the node reads a
picture from an IMAGE input like any other node.

The model is a folder under models/llm/, listed by name. Everything that
holds the model on the card is in _local_llm.py.
"""
import json

from ._local_llm import DEFAULT_CONTEXT_TOKENS, TOKEN_EVENT, generate, installed_dirs


class ai4artsed_local_llm:
    @classmethod
    def INPUT_TYPES(cls):
        dirs = installed_dirs()
        return {
            "required": {
                # Listed from disk at every validation, so a model installed
                # while ComfyUI runs is offered without a restart.
                "llm_name": (dirs or ["(no model under models/llm)"],),
                # The conversation, OpenAI-style: a JSON list of
                # {"role", "content"}. A plain string is one user message.
                "messages": ("STRING", {"multiline": True, "default": ""}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "optional": {
                "image": ("IMAGE",),
                # Pictures handed over by the DevServer: a JSON list of base64
                # strings. The IMAGE input is for a workflow; both may be
                # attached, and both reach the model.
                "images_b64": ("STRING", {"multiline": True, "default": ""}),
                "repetition_penalty": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 3.0, "step": 0.05}),
                # Prompt and answer together. 0 takes the default; the answer
                # ends with finish_reason "length" at the window, said as such.
                "context_tokens": ("INT", {"default": 0, "min": 0, "max": 1048576}),
                "stream": ("BOOLEAN", {"default": False}),
                # The messages input is raw text for the model, no chat
                # template: the completion the platform's safety check and its
                # translations were written against.
                "raw": ("BOOLEAN", {"default": False}),
                # Handed to the chat template. False closes the think block in
                # the prompt where the template has the switch (Qwen 3, 3.5,
                # 3.8, SmolLM3) and the model answers without reasoning first;
                # a template without the switch ignores it, and raw text has
                # no template.
                "enable_thinking": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("content", "thinking", "finish_reason")
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"
    OUTPUT_NODE = True

    def run(self, llm_name, messages, temperature, seed, image=None, images_b64="",
            repetition_penalty=0.0, context_tokens=0, stream=False, raw=False,
            enable_thinking=True, unique_id=None):
        conversation = None if raw else _conversation(messages)
        images = []
        if image is not None:
            images.append(image)
        if images_b64.strip():
            attached = json.loads(images_b64)
            if not isinstance(attached, list):
                raise ValueError("images_b64 has to be a JSON list of base64 strings")
            images.extend(attached)

        on_token = None
        if stream:
            # The prompt and the client the way ComfyUI's own progress hook
            # learns them (main.py, hijack_progress): the executing context
            # first, the server's record of the last prompt behind it.
            from comfy_execution.utils import get_executing_context
            from server import PromptServer
            server = PromptServer.instance
            context = get_executing_context()
            prompt_id = context.prompt_id if context is not None else server.last_prompt_id
            client_id = server.client_id

            def on_token(piece):
                server.send_sync(TOKEN_EVENT,
                                 {"prompt_id": prompt_id, "node": unique_id, "text": piece},
                                 client_id)

        answer = generate(
            llm_name, messages=conversation, prompt=messages if raw else None,
            images=images or None,
            temperature=float(temperature),
            repetition_penalty=float(repetition_penalty) if repetition_penalty > 0 else None,
            seed=int(seed),
            context_tokens=int(context_tokens) if context_tokens > 0 else DEFAULT_CONTEXT_TOKENS,
            on_token=on_token,
            enable_thinking=bool(enable_thinking),
        )
        content = answer["content"]
        thinking = answer["thinking"] or ""
        finish = answer["finish_reason"]
        return {
            # What /history carries for the DevServer. Every value is a list:
            # ComfyUI concatenates ui outputs per key.
            "ui": {
                "content": [content],
                "thinking": [thinking],
                "finish_reason": [finish],
                "prompt_tokens": [answer["prompt_tokens"]],
                "completion_tokens": [answer["completion_tokens"]],
            },
            "result": (content, thinking, finish),
        }


def _conversation(messages: str):
    """The messages input as a list of turns. JSON that is a list of turns is
    taken as it is; anything else, a text that merely begins with a bracket
    included, is one user message with that text."""
    text = messages.strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        if isinstance(parsed, list):
            if all(isinstance(m, dict) and "role" in m for m in parsed):
                return parsed
            raise ValueError("messages has to be a JSON list of {\"role\", \"content\"} turns")
    return [{"role": "user", "content": messages}]
