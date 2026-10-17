"""One reason, fit to be read by whoever is waiting.

Two clients here ask a service, get a failure back, and have to turn a response
body into something a person can read: the GPU service (`diffusers_client`) and
ComfyUI (`comfyui_ws_client`). They agreed on the requirement and then met it
twice at two strengths — one suppressed an HTML error page, the other passed it
on with the server's own file paths and version on it.

`reason_line` is that one treatment. (A third place flattens an HTML body,
`backend_router` around the cloud API call, but that one is a log-spam guard:
what it returns is the bare status, and the API's own message reaches nobody.
Different job, and a separate piece of work.)
"""

# What an error page says about itself. A body is only called one when it
# announces itself as HTML — a bare "<" is not enough: Python writes
# "<class 'Pipe'>" and "<Pipe.SD35: 1>" into perfectly good reasons, and the
# GPU service passes `str(e)` through untouched.
_HTML_MARKS = ("<html", "<!doctype html")


def reason_line(text, cap: int = 200) -> str:
    """One line, capped, with an HTML error page kept out of it.

    An HTML page from a proxy or a crashed server says nothing about the
    request and carries the server's own paths and version instead. Neither
    belongs on a workshop screen. The whole body is logged where it is read.
    """
    one = " ".join(str(text or "").split())
    low = one.lower()
    if any(m in low for m in _HTML_MARKS):
        return "an HTML error page"
    if len(one) > cap:
        return one[:cap].rstrip() + "\u2026"
    return one
