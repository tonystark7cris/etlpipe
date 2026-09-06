"""RBAC (Role-Based Access Control) execution guard for etlpipe pipelines.

Provides a pluggable, bank-grade access control layer that runs *before*
any pipeline step executes. The bank supplies their own IAM/LDAP/AD check
function — etlpipe enforces the gate but does not implement identity logic.

Usage — plugging in your bank's IAM::

    from etlpipe import Pipeline
    from etlpipe._rbac import PipelineGuard

    # Implement your own checker using LDAP, Okta, AD, or any IAM system
    def my_iam_check(pipeline_name: str, action: str) -> bool:
        current_user = os.environ.get(\"ETLPIPE_USER\", \"\")
        allowed = fetch_allowed_users_from_ldap(pipeline_name, action)
        return current_user in allowed

    guard = PipelineGuard(role_checker=my_iam_check)
    Pipeline.run(\"my_pipeline.yaml\", guard=guard)

Usage — environment variable based (simple, built-in)::

    from etlpipe._rbac import EnvRoleGuard

    # Set ETLPIPE_ALLOWED_ROLES=data_engineer,data_analyst in your env
    # Set ETLPIPE_USER_ROLE=data_engineer for the current user
    guard = EnvRoleGuard(
        allowed_roles_env=\"ETLPIPE_ALLOWED_ROLES\",
        user_role_env=\"ETLPIPE_USER_ROLE\",
    )
    Pipeline.run(\"my_pipeline.yaml\", guard=guard)
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

logger = logging.getLogger("etlpipe.rbac")


class AccessDeniedError(PermissionError):
    """Raised when pipeline execution is denied by the RBAC guard.

    Attributes:
        pipeline_name: Name of the pipeline that was denied.
        action: The action that was attempted (e.g. ``\"execute\"``).
    """

    def __init__(self, pipeline_name: str, action: str, reason: str = "") -> None:
        self.pipeline_name = pipeline_name
        self.action = action
        reason_suffix = f" ({reason})" if reason else ""
        super().__init__(
            f"Access denied: action '{action}' on pipeline '{pipeline_name}' was rejected "
            f"by the RBAC guard{reason_suffix}. "
            "Ensure you have the required role/permission or contact your data platform team."
        )


class PipelineGuard:
    """Pluggable RBAC guard for pipeline execution.

    The guard is called at the very start of :meth:`Pipeline.execute` before
    any steps run. If the check fails, :class:`AccessDeniedError` is raised
    and the pipeline is never started.

    Args:
        role_checker: A callable ``(pipeline_name: str, action: str) -> bool``.
            Return ``True`` to allow, ``False`` to deny.
            The callable may also raise its own exceptions for richer error info.
        action: The action label passed to *role_checker* (default ``\"execute\"``).

    Example::

        def my_iam(pipeline: str, action: str) -> bool:
            return current_user_has_permission(pipeline, action)

        guard = PipelineGuard(my_iam)
        guard.check(\"daily_reconciliation\")
    """

    def __init__(
        self,
        role_checker: Callable[[str, str], bool],
        action: str = "execute",
    ) -> None:
        self._checker = role_checker
        self._default_action = action

    def check(self, pipeline_name: str, action: str | None = None) -> None:
        """Check whether the pipeline action is permitted.

        Args:
            pipeline_name: The name of the pipeline being executed.
            action: The action to check. Defaults to the action set at construction.

        Raises:
            AccessDeniedError: If the role_checker returns ``False``.
        """
        effective_action = action or self._default_action
        try:
            allowed = self._checker(pipeline_name, effective_action)
        except AccessDeniedError:
            raise
        except Exception as exc:
            logger.error(
                "RBAC guard raised an unexpected exception for pipeline '%s' action '%s': %s",
                pipeline_name,
                effective_action,
                exc,
            )
            raise AccessDeniedError(
                pipeline_name, effective_action, reason=f"guard raised: {exc}"
            ) from exc

        if not allowed:
            logger.warning(
                "RBAC: access denied for pipeline '%s', action '%s'",
                pipeline_name,
                effective_action,
            )
            raise AccessDeniedError(pipeline_name, effective_action)

        logger.info(
            "RBAC: access granted for pipeline '%s', action '%s'",
            pipeline_name,
            effective_action,
        )


class AllowAllGuard(PipelineGuard):
    """No-op guard that allows all pipelines unconditionally.

    This is the default when no guard is specified, preserving backward
    compatibility. **Do not use in production environments** — replace with
    a real :class:`PipelineGuard` backed by your IAM system.
    """

    def __init__(self) -> None:
        super().__init__(role_checker=lambda _p, _a: True)

    def check(self, pipeline_name: str, action: str | None = None) -> None:
        # Skip check — always allowed
        logger.debug("AllowAllGuard: unconditionally allowing pipeline '%s'", pipeline_name)


class EnvRoleGuard(PipelineGuard):
    """Environment-variable-based RBAC guard.

    Reads a comma-separated list of allowed roles from one env var and the
    current user's role from another env var. Denies execution if the user's
    role is not in the allowed list.

    This is a lightweight built-in implementation suitable for simple
    environments. For production financial systems, replace with a real
    IAM-backed :class:`PipelineGuard`.

    Args:
        allowed_roles_env: Name of the env var containing a comma-separated
            list of allowed roles (e.g. ``\"ETLPIPE_ALLOWED_ROLES\"``).
        user_role_env: Name of the env var containing the current user's
            role (e.g. ``\"ETLPIPE_USER_ROLE\"``).

    Example::

        # Shell: export ETLPIPE_ALLOWED_ROLES=data_engineer,data_analyst
        # Shell: export ETLPIPE_USER_ROLE=data_engineer

        guard = EnvRoleGuard(
            allowed_roles_env=\"ETLPIPE_ALLOWED_ROLES\",
            user_role_env=\"ETLPIPE_USER_ROLE\",
        )
    """

    def __init__(
        self,
        allowed_roles_env: str = "ETLPIPE_ALLOWED_ROLES",
        user_role_env: str = "ETLPIPE_USER_ROLE",
    ) -> None:
        self._allowed_roles_env = allowed_roles_env
        self._user_role_env = user_role_env

        def _checker(pipeline_name: str, action: str) -> bool:
            allowed_raw = os.environ.get(allowed_roles_env, "")
            user_role = os.environ.get(user_role_env, "").strip()

            if not allowed_raw:
                logger.warning(
                    "EnvRoleGuard: '%s' is not set — defaulting to deny-all for safety.",
                    allowed_roles_env,
                )
                return False

            allowed_roles = {r.strip() for r in allowed_raw.split(",") if r.strip()}

            if not user_role:
                logger.warning(
                    "EnvRoleGuard: '%s' is not set — cannot determine user role.",
                    user_role_env,
                )
                return False

            granted = user_role in allowed_roles
            if not granted:
                logger.warning(
                    "EnvRoleGuard: role '%s' is not in allowed roles %s for pipeline '%s'",
                    user_role,
                    sorted(allowed_roles),
                    pipeline_name,
                )
            return granted

        super().__init__(role_checker=_checker)
