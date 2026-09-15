"""Route inspection helpers compatible with supported FastAPI route layouts."""

from typing import Any


def app_routes(app: Any) -> tuple[Any, ...]:
    """Return effective routes, including routes held by included routers."""

    routes: list[Any] = []
    for route in app.routes:
        effective = getattr(route, "effective_candidates", None)
        if callable(effective):
            effective = effective()
        if effective is None:
            routes.append(route)
        else:
            routes.extend(effective)
    return tuple(routes)
