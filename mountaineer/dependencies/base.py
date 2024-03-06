import warnings
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Callable

from fastapi import Request
from fastapi.dependencies.utils import get_dependant, solve_dependencies


class DependenciesBaseMeta(type):
    """
    Dependencies have to be appended to their wrapper class explicitly. Providing static
    methods confuses the FastAPI resolution pipeline, because staticfunctions don't properly
    inspect as coroutines.

    Within `solve_dependencies`, it relies on function inspection to determine whether it should
    be run in the async loop or a separate thread. Executing `is_coroutine_callable` with a static
    method will always returns False, so we will inadvertantly run async dependencies in a thread
    loop. This will just return the raw coroutine instead of actually resolving the dependency.

    Adding functions to the class directly will just link their function signatures, which
    will inspect as intended.

    """

    def __new__(cls, name, bases, namespace, **kwargs):
        # Flag any child instances as deprecated but not the base model
        if name != "DependenciesBase":
            warnings.warn(
                (
                    "DependenciesBase is deprecated and will be removed in a future version.\n"
                    "Import modules to form dependencies. See mountaineer.dependencies.core for an example."
                ),
                DeprecationWarning,
                stacklevel=2,
            )

        for attr_name, attr_value in namespace.items():
            if isinstance(attr_value, staticmethod):
                raise TypeError(
                    f"Static methods are not allowed in dependency wrapper '{name}'. Found static method: '{attr_name}'."
                )
        return super().__new__(cls, name, bases, namespace, **kwargs)


class DependenciesBase(metaclass=DependenciesBaseMeta):
    pass


@dataclass
class DependencyOverrideProvider:
    # Internally FastAPI uses a property accessor to access the dependency_overrides, so we
    # reproduce this with a simple dataclass
    dependency_overrides: dict[Callable, Callable]


@asynccontextmanager
async def get_function_dependencies(
    *,
    callable: Callable,
    url: str | None = None,
    request: Request | None = None,
    dependency_overrides: dict[Callable, Callable] | None = None,
):
    """
    Get the dependencies of a function. This will return the values that should
    be injected into the function. Provide as much metadata as possible, so we can
    resolve more accurate dependencies. If not provided, we will synthesize some values.

    :param dependency_overrides: Specify functions that should be swapped-in when resolving
    the dependency chains. This is useful during testing or when you need to override one value
    in a dependency pipeline (like a user session) with a deterministic value.

    """
    # Synthesize defaults
    if not url:
        url = "/synthetic"
    if not request:
        request = Request(
            scope={
                "type": "http",
                "path": url,
                "path_params": {},
                "query_string": "",
                "headers": [],
            }
        )

    # Synthetic request object as if we're coming from the original first page
    dependant = get_dependant(
        call=callable,
        path=url,
    )

    async with AsyncExitStack() as async_exit_stack:
        values, errors, background_tasks, sub_response, _ = await solve_dependencies(
            request=request,
            dependant=dependant,
            async_exit_stack=async_exit_stack,
            dependency_overrides_provider=(
                DependencyOverrideProvider(dependency_overrides=dependency_overrides)
                if dependency_overrides
                else None
            ),
        )
        if background_tasks:
            raise RuntimeError(
                "Background tasks are not supported when calling a static function, due to undesirable side-effects."
            )
        if errors:
            raise RuntimeError(
                f"Errors encountered while resolving dependencies: {errors}"
            )

        yield values
