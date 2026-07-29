"""Resolve AliveWorld feature uses to enabled provider profiles."""

from __future__ import annotations

from .models import TASK_SPECS, ConnectionSnapshot, ResolvedConnection, TaskRoute


class RouteResolutionError(ValueError):
    pass


def resolve_connection(
    snapshot: ConnectionSnapshot,
    task: str,
) -> ResolvedConnection | None:
    if task not in TASK_SPECS:
        raise RouteResolutionError(f"未知功能用途：{task}")

    current = task
    visited: set[str] = set()
    model_override = ""
    while True:
        if current in visited:
            raise RouteResolutionError(f"功能用途继承形成循环：{task}")
        visited.add(current)
        route = snapshot.routes.get(current)
        if route is None:
            spec = TASK_SPECS[current]
            route = TaskRoute(inherit_from=spec["inherit_from"])
        if not model_override and route.model_override:
            model_override = route.model_override
        if route.connection_id:
            profile = snapshot.profiles.get(route.connection_id)
            if not profile:
                raise RouteResolutionError(
                    f"{TASK_SPECS[current]['label']} 指向不存在的接口：{route.connection_id}"
                )
            if not profile.enabled:
                return None
            expected = TASK_SPECS[task]["category"]
            if profile.category != expected:
                raise RouteResolutionError(
                    f"{TASK_SPECS[task]['label']} 需要 {expected} 接口，"
                    f"但“{profile.name}”属于 {profile.category}"
                )
            model = model_override or profile.default_model
            return ResolvedConnection(task=task, profile=profile, model=model)
        parent = route.inherit_from or TASK_SPECS[current]["inherit_from"]
        if not parent:
            return None
        if parent not in TASK_SPECS:
            raise RouteResolutionError(f"{TASK_SPECS[current]['label']} 继承了未知用途：{parent}")
        current = parent
