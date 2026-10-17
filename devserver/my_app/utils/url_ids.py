"""An integer in a URL ends where SQLite's INTEGER ends (2026-09-24).

Werkzeug's `int` converter takes a number of any length. A path id above
2**63 - 1 names no row of the lab database, and binding it to a query raises
OverflowError, which Flask answers with a 500. With `RowIdConverter` as the
app's `int`, such a path answers 404.
"""
from werkzeug.exceptions import NotFound
from werkzeug.routing import IntegerConverter

# The largest value SQLite's INTEGER holds.
MAX_ROW_ID = 2**63 - 1


class RowIdConverter(IntegerConverter):
    """`<int:...>` that answers 404 above `MAX_ROW_ID`.

    It raises NotFound: Werkzeug's matcher turns a ValidationError into 405
    when another rule on the same path takes another method, as `PUT` does
    beside `DELETE /api/courses/<id>/access`."""

    def to_python(self, value):
        number = super().to_python(value)
        if number > MAX_ROW_ID:
            raise NotFound()
        return number


def install_row_id_converter(app) -> None:
    """Make `RowIdConverter` the app's `int`. A rule takes its converter when
    it is added, so this runs before the first blueprint is registered."""
    app.url_map.converters["int"] = RowIdConverter
