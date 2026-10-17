"""
The nodes' LLM calls go through the DevServer, which acts as their LLM proxy:
POST /api/chat/proxy resolves the model, holds the keys and
the provider table, and applies the fallback the settings page regulates
(the "as fallback" box per provider column, read by
build_model_candidate_chain for every role-based call). A node knows no
provider, no key and no model id.

A model dropdown offers the node's role on the platform first,
"platform/<ROLE>" (platform/STAGE2_INTERCEPTION_MODEL, ...): the settings'
model for that job, with the settings' fallback chain behind it. Then every
model this installation offers (GET /api/chat/models), by the id the
DevServer wants; such a model runs exactly, one attempt, no fallback, the
platform's rule for a model picked by hand.

Where the DevServer answers: AI4ARTSED_DEVSERVER_URL, else
http://127.0.0.1:<PORT>, PORT being the variable server.py reads, with
config.py's default (17802, the development port). A ComfyUI that does not
run in the DevServer's environment (production answers on 17801) needs one of
the two variables set.
"""

import os
import requests

ROLE_PREFIX = "platform/"
_DEFAULT_PORT = "17802"


def devserver_url():
    url = os.environ.get("AI4ARTSED_DEVSERVER_URL", "").strip()
    if not url:
        url = f"http://127.0.0.1:{os.environ.get('PORT', _DEFAULT_PORT)}"
    return url.rstrip("/")


def model_choices(role):
    """What a node's model dropdown offers, read at ComfyUI's start and again
    at every validation: the node's role, then the DevServer's list. Where the
    DevServer does not answer, the role alone, with a line on the console; the
    node still registers, and a workflow naming a model id then fails
    ComfyUI's validation until the DevServer is up."""
    choices = [f"{ROLE_PREFIX}{role}"]
    url = devserver_url()
    try:
        response = requests.get(f"{url}/api/chat/models", timeout=5)
        response.raise_for_status()
        choices += [m["id"] for m in response.json().get("models", []) if m.get("id")]
    except Exception as e:
        print(f"[AI4ArtsEd nodes] DevServer at {url} did not list its models ({e}); "
              f"the dropdown offers {choices[0]} alone")
    return choices


def chat(node_label, messages, model, temperature=None, image_b64=None):
    """One LLM call through the DevServer: (content, model_used). Raises with
    the DevServer's answer where the call failed; no other model answers in a
    node's place, and no error text goes downstream as the result. No read
    timeout on the call (rule 5), a connect timeout only.

    A node runs inside ComfyUI's executor, and the DevServer runs a local
    model BY ComfyUI, one prompt at a time (ai4artsed_local_llm): a prompt it
    queued for this call would wait behind the one this node is part of. So
    the call says where it runs from ("runs_inside_comfyui"), and where the
    DevServer's chain reaches a local model it answers with the instruction
    to run it here ("run_in_caller": the model's folder, the messages as the
    chain fitted them, the picture where the model reads one), and the node
    runs it with the runner the DevServer's own calls go through."""
    url = devserver_url()
    payload = {"messages": messages, "model": model, "runs_inside_comfyui": True}
    if temperature is not None:
        payload["temperature"] = temperature
    if image_b64:
        payload["image_b64"] = image_b64
    try:
        response = requests.post(f"{url}/api/chat/proxy", json=payload, timeout=(10, None))
    except requests.RequestException as e:
        raise Exception(f"[{node_label}] DevServer at {url} not reached: {e}")
    if response.status_code != 200:
        try:
            detail = response.json().get("error") or response.text
        except Exception:
            detail = response.text
        raise Exception(f"[{node_label}] DevServer answered {response.status_code} for {model}: {detail}")
    data = response.json()
    local = data.get("run_in_caller")
    if local:
        from ._local_llm import generate
        answer = generate(
            local["llm_name"], messages=local["messages"],
            images=[local["image_b64"]] if local.get("image_b64") else None,
            temperature=0.7 if temperature is None else float(temperature))
        return answer["content"], data.get("model_used", model)
    return data.get("content", ""), data.get("model_used", model)
