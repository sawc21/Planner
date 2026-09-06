from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.templating import Jinja2Templates

from semester_ops.application.study import MAX_ASSIGNMENT_DOCUMENT_BYTES
from semester_ops.web.security import csrf_token, require_csrf, safe_return_path
from semester_ops.web.services import (
    AssignmentDocumentUploadCommand,
    BlockCreateCommand,
    BlockEditCommand,
    MealItemCommand,
    SettingsCommand,
    WebServices,
    WorkoutSetCommand,
)

router = APIRouter()


def get_web_services(request: Request) -> Iterator[WebServices]:
    with request.app.state.service_factory() as services:
        yield services


def render_page(
    request: Request,
    template_name: str,
    view_data: Mapping[str, Any] | None = None,
    *,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    templates: Jinja2Templates = request.app.state.templates
    context: dict[str, Any] = dict(view_data or {})
    context.update(
        request=request,
        csrf_token=csrf_token(request),
        current_path=request.url.path,
        nav_path=context.get("nav_path", request.url.path),
        flash=request.session.pop("flash", None),
    )
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
        status_code=status_code,
    )


def set_flash(request: Request, message: str, *, tone: str = "success") -> None:
    request.session["flash"] = {"message": message, "tone": tone}


def redirect_back(request: Request, return_to: str | None, fallback: str = "/") -> RedirectResponse:
    return RedirectResponse(
        safe_return_path(return_to, fallback),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/", response_class=HTMLResponse, name="today")
def today_page(
    request: Request,
    day: Annotated[date | None, Query()] = None,
    services: WebServices = Depends(get_web_services),
) -> HTMLResponse:
    return render_page(request, "today.html", services.get_today(day))


@router.get("/week", response_class=HTMLResponse, name="week")
def week_page(
    request: Request,
    anchor: Annotated[date | None, Query()] = None,
    services: WebServices = Depends(get_web_services),
) -> HTMLResponse:
    return render_page(request, "week.html", services.get_week(anchor))


@router.get("/assignments", response_class=HTMLResponse, name="assignments")
def assignments_page(
    request: Request,
    state: Annotated[str | None, Query()] = None,
    services: WebServices = Depends(get_web_services),
) -> HTMLResponse:
    return render_page(request, "assignments.html", services.list_assignments(state))


@router.get("/assignments/{assignment_id}", response_class=HTMLResponse, name="assignment_study")
def assignment_study_page(
    request: Request,
    assignment_id: str,
    services: WebServices = Depends(get_web_services),
) -> HTMLResponse:
    return render_page(
        request,
        "assignment_study.html",
        services.get_assignment_study(assignment_id),
    )


@router.get("/assignments/{assignment_id}/documents/{document_id}")
def download_assignment_document(
    assignment_id: str,
    document_id: str,
    services: WebServices = Depends(get_web_services),
) -> Response:
    document = services.get_assignment_document(assignment_id, document_id)
    return Response(
        document.content,
        media_type=document.media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.filename)}"},
    )


@router.get("/imports", response_class=HTMLResponse, name="imports")
def imports_page(
    request: Request,
    services: WebServices = Depends(get_web_services),
) -> HTMLResponse:
    return render_page(request, "imports.html", services.list_imports())


@router.get("/imports/{draft_id}", response_class=HTMLResponse, name="import_detail")
def import_detail_page(
    request: Request,
    draft_id: str,
    services: WebServices = Depends(get_web_services),
) -> HTMLResponse:
    return render_page(request, "import_detail.html", services.get_import(draft_id))


@router.get("/settings", response_class=HTMLResponse, name="settings")
def settings_page(
    request: Request,
    services: WebServices = Depends(get_web_services),
) -> HTMLResponse:
    return render_page(request, "settings.html", services.get_settings_view())


@router.get("/blocks/new", response_class=HTMLResponse, name="new_block")
def new_block_page(
    request: Request,
    day: Annotated[date | None, Query()] = None,
    return_to: Annotated[str | None, Query()] = None,
    services: WebServices = Depends(get_web_services),
) -> HTMLResponse:
    view_data = dict(services.get_new_block(day))
    view_data["return_to"] = safe_return_path(return_to, "/")
    view_data["nav_path"] = view_data["return_to"]
    return render_page(request, "new_block.html", view_data)


@router.get("/blocks/{block_id}/edit", response_class=HTMLResponse, name="edit_block")
def edit_block_page(
    request: Request,
    block_id: str,
    return_to: Annotated[str | None, Query()] = None,
    services: WebServices = Depends(get_web_services),
) -> HTMLResponse:
    view_data = dict(services.get_block(block_id))
    view_data["return_to"] = safe_return_path(return_to, "/")
    view_data["nav_path"] = view_data["return_to"]
    return render_page(request, "edit_block.html", view_data)


@router.post("/blocks", dependencies=[Depends(require_csrf)])
def create_block(
    request: Request,
    title: Annotated[str, Form(min_length=1, max_length=160)],
    planned_start_local: Annotated[datetime, Form()],
    planned_end_local: Annotated[datetime, Form()],
    category: Annotated[str, Form(min_length=1, max_length=40)],
    flexibility: Annotated[str, Form(pattern="^(fixed|flexible|optional)$")],
    notes: Annotated[str | None, Form(max_length=4000)] = None,
    project_to_calendar: Annotated[bool, Form()] = False,
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    if planned_end_local <= planned_start_local:
        raise ValueError("End time must be after start time.")
    services.create_block(
        BlockCreateCommand(
            title=title.strip(),
            planned_start_local=planned_start_local,
            planned_end_local=planned_end_local,
            category=category,
            flexibility=flexibility,
            notes=notes.strip() if notes else None,
            project_to_calendar=project_to_calendar,
        )
    )
    set_flash(request, "Schedule block created.")
    return redirect_back(request, return_to)


@router.post("/blocks/{block_id}/duplicate", dependencies=[Depends(require_csrf)])
def duplicate_block(
    request: Request,
    block_id: str,
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    safe_return = safe_return_path(return_to, "/")
    duplicate_id = services.duplicate_block(block_id)
    set_flash(request, "Independent copy created. Adjust its time and details.")
    location = f"/blocks/{duplicate_id}/edit?{urlencode({'return_to': safe_return})}"
    return RedirectResponse(location, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/blocks/{block_id}/delete", dependencies=[Depends(require_csrf)])
def delete_block(
    request: Request,
    block_id: str,
    confirmation: Annotated[bool, Form()],
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    if not confirmation:
        raise ValueError("Block removal must be confirmed.")
    services.delete_block(block_id)
    set_flash(request, "Schedule block removed.")
    return redirect_back(request, return_to)


@router.post("/blocks/{block_id}/status", dependencies=[Depends(require_csrf)])
def set_block_status(
    request: Request,
    block_id: str,
    action: Annotated[str, Form()],
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    if action not in {"start", "complete", "skip", "reopen"}:
        raise ValueError(f"Unknown block action: {action}")
    result = services.set_block_status(block_id, action)
    message = str((result or {}).get("message", f"Block {action}ed."))
    set_flash(request, message)
    return redirect_back(request, return_to)


@router.post("/blocks/{block_id}/move", dependencies=[Depends(require_csrf)])
def move_block(
    request: Request,
    block_id: str,
    minutes: Annotated[int, Form(ge=-1440, le=1440)],
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    if minutes == 0 or minutes % 15:
        raise ValueError("Blocks can be moved only in non-zero 15-minute increments.")
    services.move_block(block_id, minutes)
    direction = "later" if minutes > 0 else "earlier"
    set_flash(request, f"Block moved {abs(minutes)} minutes {direction}.")
    return redirect_back(request, return_to)


@router.post("/blocks/{block_id}/edit", dependencies=[Depends(require_csrf)])
def update_block(
    request: Request,
    block_id: str,
    title: Annotated[str, Form(min_length=1, max_length=160)],
    planned_start_local: Annotated[datetime, Form()],
    planned_end_local: Annotated[datetime, Form()],
    category: Annotated[str, Form(min_length=1, max_length=40)],
    flexibility: Annotated[str, Form(pattern="^(fixed|flexible|optional)$")],
    notes: Annotated[str | None, Form(max_length=4000)] = None,
    project_to_calendar: Annotated[bool, Form()] = False,
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    if planned_end_local <= planned_start_local:
        raise ValueError("End time must be after start time.")
    services.update_block(
        block_id,
        BlockEditCommand(
            title=title.strip(),
            planned_start_local=planned_start_local,
            planned_end_local=planned_end_local,
            category=category,
            flexibility=flexibility,
            notes=notes.strip() if notes else None,
            project_to_calendar=project_to_calendar,
        ),
    )
    set_flash(request, "Schedule block updated.")
    return redirect_back(request, return_to)


@router.post("/checklist-items/{item_id}", dependencies=[Depends(require_csrf)])
def update_checklist_item(
    request: Request,
    item_id: str,
    completed: Annotated[bool, Form()] = False,
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    services.set_checklist_item(item_id, completed=completed)
    return redirect_back(request, return_to)


@router.post("/meal-items/{item_id}", dependencies=[Depends(require_csrf)])
def update_meal_item(
    request: Request,
    item_id: str,
    completed: Annotated[bool, Form()] = False,
    consumed_quantity: Annotated[Decimal | None, Form(gt=0)] = None,
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    services.set_meal_item(
        item_id,
        MealItemCommand(completed=completed, consumed_quantity=consumed_quantity),
    )
    return redirect_back(request, return_to)


@router.post("/workout-sets/{set_id}", dependencies=[Depends(require_csrf)])
def update_workout_set(
    request: Request,
    set_id: str,
    completed: Annotated[bool, Form()] = False,
    actual_reps: Annotated[int | None, Form(ge=0, le=1000)] = None,
    actual_weight: Annotated[Decimal | None, Form(ge=0)] = None,
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    services.set_workout_set(
        set_id,
        WorkoutSetCommand(
            completed=completed,
            actual_reps=actual_reps,
            actual_weight=actual_weight,
        ),
    )
    return redirect_back(request, return_to)


@router.post("/assignments/{assignment_id}/state", dependencies=[Depends(require_csrf)])
def update_assignment_state(
    request: Request,
    assignment_id: str,
    assignment_state: Annotated[
        str,
        Form(alias="state", pattern="^(inbox|planned|completed|ignored)$"),
    ],
    estimated_minutes: Annotated[int | None, Form(ge=1, le=10080)] = None,
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    services.set_assignment_state(
        assignment_id,
        state=assignment_state,
        estimated_minutes=estimated_minutes,
    )
    set_flash(request, "Assignment updated.")
    return redirect_back(request, return_to, "/assignments")


@router.post(
    "/assignments/{assignment_id}/documents",
    dependencies=[Depends(require_csrf)],
)
async def upload_assignment_document(
    request: Request,
    assignment_id: str,
    document: Annotated[UploadFile, File()],
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    try:
        content = await document.read(MAX_ASSIGNMENT_DOCUMENT_BYTES + 1)
    finally:
        await document.close()
    services.upload_assignment_document(
        assignment_id,
        AssignmentDocumentUploadCommand(
            filename=document.filename or "",
            media_type=document.content_type,
            content=content,
        ),
    )
    set_flash(request, "Document attached and study quiz regenerated.")
    return RedirectResponse(f"/assignments/{assignment_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post(
    "/assignments/{assignment_id}/study/regenerate",
    dependencies=[Depends(require_csrf)],
)
def regenerate_assignment_study(
    request: Request,
    assignment_id: str,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    services.regenerate_assignment_study(assignment_id)
    set_flash(request, "Study guide and quiz regenerated from the attached documents.")
    return RedirectResponse(f"/assignments/{assignment_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post(
    "/assignments/{assignment_id}/quiz/check",
    dependencies=[Depends(require_csrf)],
    response_class=HTMLResponse,
)
async def check_assignment_quiz(
    request: Request,
    assignment_id: str,
    services: WebServices = Depends(get_web_services),
) -> HTMLResponse:
    form = await request.form()
    answers = {
        key.removeprefix("answer_"): str(value)
        for key, value in form.items()
        if key.startswith("answer_")
    }
    view_data = services.check_assignment_quiz(assignment_id, answers)
    return render_page(request, "assignment_study.html", view_data)


@router.post("/imports/{draft_id}/approve", dependencies=[Depends(require_csrf)])
def approve_import(
    request: Request,
    draft_id: str,
    allow_warnings: Annotated[bool, Form()] = False,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    result = services.approve_import(draft_id, allow_warnings=allow_warnings)
    message = str(result.get("message", "Import applied successfully."))
    set_flash(request, message)
    return RedirectResponse("/imports", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/imports/{draft_id}/reject", dependencies=[Depends(require_csrf)])
def reject_import(
    request: Request,
    draft_id: str,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    services.reject_import(draft_id)
    set_flash(request, "Draft rejected. Live schedule unchanged.", tone="neutral")
    return RedirectResponse("/imports", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/settings", dependencies=[Depends(require_csrf)])
def update_settings(
    request: Request,
    timezone: Annotated[str, Form()] = "America/Chicago",
    operational_day_start: Annotated[str, Form(pattern="^([01]\\d|2[0-3]):[0-5]\\d$")] = "04:00",
    missed_grace_minutes: Annotated[int, Form(ge=0, le=1440)] = 30,
    calorie_target: Annotated[int | None, Form(ge=0, le=20000)] = None,
    protein_target_grams: Annotated[int | None, Form(ge=0, le=2000)] = None,
    weight_unit: Annotated[str, Form(pattern="^(lb|kg)$")] = "lb",
    blackboard_ics_url: Annotated[str | None, Form(max_length=4096)] = None,
    clear_blackboard_ics: Annotated[bool, Form()] = False,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    services.update_settings(
        SettingsCommand(
            timezone=timezone,
            operational_day_start=operational_day_start,
            missed_grace_minutes=missed_grace_minutes,
            calorie_target=calorie_target,
            protein_target_grams=protein_target_grams,
            weight_unit=weight_unit,
            blackboard_ics_url=blackboard_ics_url.strip() if blackboard_ics_url else None,
            clear_blackboard_ics=clear_blackboard_ics,
        )
    )
    set_flash(request, "Settings saved.")
    return RedirectResponse("/settings", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/sync", dependencies=[Depends(require_csrf)])
def sync_now(
    request: Request,
    return_to: Annotated[str | None, Form()] = None,
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    result = services.sync_now()
    tone = str(result.get("tone", "success"))
    message = str(result.get("message", "Synchronization finished."))
    set_flash(request, message, tone=tone)
    return redirect_back(request, return_to, "/settings")


@router.post("/sync-conflicts/{conflict_id}/resolve", dependencies=[Depends(require_csrf)])
def resolve_sync_conflict(
    request: Request,
    conflict_id: str,
    resolution: Annotated[str, Form(pattern="^(keep_planner|use_remote)$")],
    services: WebServices = Depends(get_web_services),
) -> RedirectResponse:
    result = services.resolve_sync_conflict(conflict_id, resolution)
    set_flash(request, str(result.get("message", "Calendar conflict resolved.")))
    return RedirectResponse("/settings", status_code=status.HTTP_303_SEE_OTHER)
