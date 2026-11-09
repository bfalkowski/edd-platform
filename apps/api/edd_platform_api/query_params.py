from __future__ import annotations

from fastapi import HTTPException, Request


def reject_unknown_query_params(request: Request) -> None:
    """Return 400 for a query parameter the route does not declare, instead of ignoring it.

    An ignored filter makes a list route return every record, which reads as the filtered answer.
    """
    supported = sorted(param.alias for param in request.scope["route"].dependant.query_params)
    unknown = sorted(set(request.query_params) - set(supported))
    if unknown:
        noun = "parameter" if len(unknown) == 1 else "parameters"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported query {noun}: {', '.join(unknown)}. "
                f"Supported query parameters: {', '.join(supported)}."
            ),
        )
