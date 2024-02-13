from datetime import datetime
from typing import Type, TypeVar
from uuid import UUID

from sqlmodel import Field, SQLModel


class QueableItemMixin(SQLModel):
    """
    Mixin for items that can be queued.
    """

    workflow_name: str
    status: str = "queued"


class DaemonWorkflowInstance(QueableItemMixin, SQLModel):
    """
    One given instance of a workflow execution.
    """

    id: int | None = Field(default=None, primary_key=True)

    # Will couple with the defined Workflow
    registry_id: str
    input_body: str  # json input

    # Status metadata
    launch_time: datetime
    end_time: datetime | None = None
    current_worker_status_id: int | None = None

    # Exit status
    exception: str | None = None
    exception_stack: str | None = None
    result_body: str | None = None


class WorkerStatus(SQLModel):
    """
    Current status of the worker.
    """

    id: int | None = Field(default=None, primary_key=True)

    # Internal process ID generated by each worker
    internal_process_id: UUID

    launch_time: datetime
    last_ping: datetime


class DaemonAction(QueableItemMixin, SQLModel):
    """
    One given action call, can potentially have multiple repeats depending on the backoff event.
    """

    id: int | None = Field(default=None, primary_key=True)
    instance_id: int

    # Event-sourced state identifier, will be mirrored across multiple instance runs if necessary
    state: str

    registry_id: str
    input_body: str  # json payload

    # The most recent DaemonActionResult. If there is an exit condition, this
    # will be the final result.
    final_result_id: int | None = None

    # Timeout preferences, in seconds
    wall_soft_timeout: int | None = None
    wall_hard_timeout: int | None = None
    cpu_soft_timeout: int | None = None
    cpu_hard_timeout: int | None = None

    # Don't schedule before this time interval
    schedule_after: datetime | None = None


class DaemonActionResult(SQLModel):
    """
    Represents the potentially one:many executions of the daemon actions.
    """

    id: int | None = Field(default=None, primary_key=True)
    action_id: int

    # Exit status
    exception: str | None = None
    exception_stack: str | None = None
    result_body: str | None = None


DaemonWorkflowInstanceType = TypeVar(
    "DaemonWorkflowInstanceType", bound=DaemonWorkflowInstance
)
WorkerStatusType = TypeVar("WorkerStatusType", bound=WorkerStatus)
DaemonActionType = TypeVar("DaemonActionType", bound=DaemonAction)
DaemonActionResultType = TypeVar("DaemonActionResultType", bound=DaemonActionResult)


class LocalModelDefinition:
    """
    Wrapper class to let downstream clients
    define their own model types.
    """

    def __init__(
        self,
        DaemonWorkflowInstance: Type[DaemonWorkflowInstanceType],
        WorkerStatus: Type[WorkerStatusType],
        DaemonAction: Type[DaemonActionType],
        DaemonActionResult: Type[DaemonActionResultType],
    ):
        self.DaemonWorkflowInstance = DaemonWorkflowInstance
        self.WorkerStatus = WorkerStatus
        self.DaemonAction = DaemonAction
        self.DaemonActionResult = DaemonActionResult
