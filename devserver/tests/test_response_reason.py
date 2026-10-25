"""One line, and never a server's own error page.

Two clients turn a failed response into something a person reads: the GPU
service's and ComfyUI's. Both used to do it themselves, at different strengths
— one suppressed an HTML error page, the other passed it on, with the server's
file paths and version on it, onto a workshop screen.

The tests here hold the one treatment in place, and hold it back from claiming
too much: "an HTML error page" is a statement ABOUT the answer, and Python
writes plenty of good reasons that merely start with a pointy bracket.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from my_app.utils.response_reason import reason_line


NGINX = ("<html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>\r\n"
         "<center><h1>502 Bad Gateway</h1></center>\r\n"
         "<hr><center>nginx/1.24.0</center>\r\n</body>\r\n</html>\r\n")

APACHE = ('<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">\n<html><head>\n'
          "<title>500 Internal Server Error</title>\n</head><body>\n"
          "<address>Apache/2.4.6 (CentOS) Server at /srv/app Port 80</address>\n"
          "</body></html>\n")


class TestAnErrorPageStaysWhereItIs:

    @pytest.mark.parametrize("page", [NGINX, APACHE])
    def test_nothing_of_it_travels(self, page):
        got = reason_line(page)
        assert got == "an HTML error page"
        assert "nginx" not in got and "Apache" not in got and "/srv/" not in got

    def test_the_log_is_where_it_belongs(self):
        """This is the whole reason the treatment exists: what a page carries
        is the server's own paths and version, and it says nothing about the
        request. Whoever reads logs still gets the body, beside the line."""
        assert "502" not in reason_line(NGINX)


class TestAReasonThatMerelyLooksLikeMarkup:
    """`str(e)` from the GPU service comes through untouched, and Python puts
    a repr in plenty of them. Calling those an error page states something
    false about the answer, and hides the actual cause."""

    @pytest.mark.parametrize("said", [
        "<class 'diffusers.StableDiffusion3Pipeline'>",
        "<Pipe.SD35: 1>",
        "<object object at 0x7fe74af91650>",
        "expected a request <body> with a model_id",
        "the prompt contains markup: <header>x</header>",
    ])
    def test_it_comes_through(self, said):
        assert reason_line(said) == said


class TestTheLine:

    def test_it_is_one_line(self):
        assert reason_line("500 Internal Server Error\n\nServer got itself in trouble") == (
            "500 Internal Server Error Server got itself in trouble")

    def test_it_is_capped_and_says_that_it_was(self):
        got = reason_line("x" * 400, 200)
        assert len(got) == 201
        assert got.endswith("…")

    def test_a_short_reason_is_left_alone(self):
        assert reason_line("model not found", 200) == "model not found"

    @pytest.mark.parametrize("nothing", ["", "   ", None])
    def test_nothing_stays_nothing(self, nothing):
        """The callers decide what to say instead — they know what they asked."""
        assert reason_line(nothing) == ""


def test_both_readers_use_it():
    """Rule #13: one treatment, not a copy per client."""
    import ast
    from pathlib import Path
    services = Path(__file__).resolve().parents[1] / "my_app" / "services"
    for name in ("comfyui_ws_client.py", "diffusers_client.py"):
        src = (services / name).read_text(encoding="utf-8")
        assert "response_reason" in src, "%s reads bodies without the shared line" % name
        tree = ast.parse(src)
        assert any(isinstance(n, ast.Name) and n.id == "reason_line" for n in ast.walk(tree)), \
            "%s imports the shared line and does not call it" % name
