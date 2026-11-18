"""Public API layer.

* ``v1/``, ``v2/``: each version's contract (pydantic schemas + mappers). Frozen.
* ``routes.py``: every handler, tagged with the versions it serves.
* ``apps.py``: one FastAPI app per version, built from those tags.
"""
