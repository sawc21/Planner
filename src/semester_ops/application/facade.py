import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from semester_ops.application.common import add_audit_event, get_or_create_settings
from semester_ops.application.errors import NotFoundError, ValidationError
from semester_ops.application.imports import ImportService
from semester_ops.application.schedule import ScheduleService
from semester_ops.application.study import AssignmentStudyService, QuizResult
from semester_ops.application.study_contract import assignment_study_schema
from semester_ops.application.sync import (
    BlackboardAssignmentSync,
    ConnectorSynchronizer,
    GoogleCalendarProjectionSync,
    SyncService,
)
from semester_ops.application.tracking import TrackingService
from semester_ops.config import get_settings as get_runtime_settings
from semester_ops.db.models import (
    Assignment,
    AssignmentBlockLink,
    BlockOccurrence,
    CalendarEventLink,
    ChecklistItem,
    ExternalSourceState,
    ImportDraft,
    SyncConflict,
    SyncRun,
    utc_now,
)
from semester_ops.domain.enums import (
    AssignmentInboxStatus,
    BlockCategory,
    Flexibility,
    SyncConflictStatus,
    SyncConnector,
    TrackingStatus,
)
from semester_ops.domain.time import operational_day_bounds, resolve_wall_time
from semester_ops.domain.tracking import effective_status
from semester_ops.integrations.blackboard import (
    BlackboardFeedClient,
    validate_blackboard_feed_url,
)
from semester_ops.integrations.google_calendar import (
    GoogleCalendarConfigurationError,
    GoogleCalendarGateway,
)

_GOOGLE_RECOVERY_BY_CODE = {
    "oauth_required": "Run Google setup with --reauthorize, then press Sync now again.",
    "oauth_refresh_failed": "Run Google setup with --reauthorize, then press Sync now again.",
    "calendar_not_found": (
        "The saved development calendar is unavailable. Stop syncing and rebuild the "
        "development calendar before continuing."
    ),
    "calendar_permission_denied": (
        "Confirm the Google account owns Semester Ops - Dev, then reauthorize."
    ),
    "calendar_rate_limited": "Wait a few minutes, then press Sync now again.",
    "calendar_temporarily_unavailable": (
        "Check the network connection, then press Sync now again."
    ),
    "calendar_read_failed": "Run Google setup with --reauthorize, then try again.",
}


@dataclass(frozen=True, slots=True)
class _MealGuide:
    name: str
    aliases: tuple[str, ...]
    ingredients: str
    steps: tuple[str, ...]


# These guides are a presentation fallback for the recipes in the supplied seven-day
# source schedule. Labeled ingredients or steps stored on a block always take priority.
_MEAL_GUIDES = (
    _MealGuide(
        name="Southwest breakfast tacos",
        aliases=("southwest breakfast tacos",),
        ingredients=(
            "3 eggs; 2 small whole-grain tortillas; 2 oz chicken or turkey sausage; "
            "1 small potato; 1/4 cup black beans; 1/4 bell pepper; diced onion; "
            "2 tbsp shredded cheese; salsa"
        ),
        steps=(
            "Dice the potato and microwave it with a splash of water for 3-4 minutes.",
            (
                "Brown the potato and sausage for 4-5 minutes; add pepper and onion "
                "for the last 2 minutes."
            ),
            "Scramble the eggs into the skillet, then warm the tortillas.",
            "Fill the tortillas with the egg mixture, beans, cheese, and salsa.",
        ),
    ),
    _MealGuide(
        name="Turkey-avocado club wrap",
        aliases=(
            "turkey avocado club wrap",
            "turkey avocado and bacon style club wrap",
        ),
        ingredients=(
            "1 large whole-grain wrap; 5 oz sliced turkey; 2 slices turkey bacon; "
            "1/4 avocado; tomato; spinach or lettuce; 1 slice cheese; mustard; "
            "apple or orange"
        ),
        steps=(
            "Crisp the turkey bacon according to its package directions.",
            (
                "Spread mustard on the wrap and add turkey, bacon, avocado, tomato, "
                "greens, and cheese."
            ),
            "Fold the sides, roll tightly, and toast seam-side down for 1-2 minutes per side.",
        ),
    ),
    _MealGuide(
        name="Lemon-Parmesan chicken, potatoes, and green beans",
        aliases=("lemon parmesan chicken",),
        ingredients=(
            "6 oz chicken breast or boneless thigh; 10 oz baby potatoes; "
            "1.5 cups green beans; 2 tsp olive oil; 1/2 lemon; garlic; Parmesan; "
            "Italian seasoning; salt; pepper"
        ),
        steps=(
            "Heat the oven to 425 F. Season the halved potatoes and roast them for 15 minutes.",
            (
                "Season the chicken with garlic, lemon zest, and Italian seasoning; "
                "add it with the green beans."
            ),
            "Roast for 18-22 minutes more, until the chicken reaches 165 F and the potatoes brown.",
            "Finish with lemon juice and Parmesan.",
        ),
    ),
    _MealGuide(
        name="Cinnamon-banana protein French toast",
        aliases=("cinnamon banana protein french toast",),
        ingredients=(
            "3 slices whole-grain bread; 2 eggs; 1/2 cup liquid egg whites; "
            "1/2 banana; cinnamon; vanilla; milk; berries; peanut butter or maple syrup"
        ),
        steps=(
            "Whisk the eggs, egg whites, milk, cinnamon, and vanilla in a shallow bowl.",
            "Dip each bread slice until coated but still firm.",
            "Cook in a lightly greased skillet over medium heat for 2-3 minutes per side.",
            "Top with banana, berries, and peanut butter or a little syrup.",
        ),
    ),
    _MealGuide(
        name="Fresh chicken Caesar wrap",
        aliases=("fresh chicken caesar wrap", "chicken caesar wrap"),
        ingredients=(
            "5-6 oz thin chicken breast; 1 large whole-grain wrap; romaine; tomato; "
            "Parmesan; 2 tbsp Greek-yogurt Caesar dressing"
        ),
        steps=(
            "Season the chicken with salt, pepper, garlic powder, and paprika.",
            "Sear for 4-5 minutes per side, until it reaches 165 F; rest and slice.",
            (
                "Toss romaine with dressing and Parmesan, add the chicken and tomato, "
                "then roll and briefly toast the wrap."
            ),
        ),
    ),
    _MealGuide(
        name="Beef and broccoli stir-fry with rice",
        aliases=("beef and broccoli stir fry",),
        ingredients=(
            "6 oz lean sirloin; 2 cups broccoli; 1 cup cooked rice; 1 tsp oil; "
            "2 tbsp low-sodium soy sauce; 1 tsp honey; garlic; ginger; "
            "1 tsp cornstarch; 1/3 cup water"
        ),
        steps=(
            "Start the rice and whisk together the sauce ingredients.",
            "Cook the beef in one layer in a hot oiled skillet for 2-3 minutes, then remove it.",
            "Steam the broccoli with a splash of water for 2 minutes, then uncover.",
            (
                "Return the beef, add the sauce, and stir for 1-2 minutes until glossy; "
                "serve over rice."
            ),
        ),
    ),
    _MealGuide(
        name="Huevos rancheros with black beans",
        aliases=("huevos rancheros",),
        ingredients=(
            "3 eggs; 2 corn tortillas; 1/2 cup black beans; 1/2 cup salsa; "
            "1/4 avocado; 2 tbsp crumbled cheese; cilantro"
        ),
        steps=(
            "Warm the beans and salsa together in a small pan.",
            "Warm the tortillas in a dry skillet, then cook the eggs as preferred.",
            "Layer the tortillas, beans and salsa, eggs, avocado, cheese, and cilantro.",
        ),
    ),
    _MealGuide(
        name="Mediterranean chicken pita with tzatziki",
        aliases=("mediterranean chicken pita",),
        ingredients=(
            "5 oz chicken breast; 1 whole-grain pita; tomato; cucumber; red onion; "
            "spinach; 2 tbsp feta; 2 tbsp hummus; Greek yogurt; lemon; garlic; "
            "dill or parsley"
        ),
        steps=(
            (
                "Season the chicken with oregano, garlic, paprika, lemon, salt, and "
                "pepper; sear 4-5 minutes per side."
            ),
            "Mix Greek yogurt, grated cucumber, lemon, garlic, salt, and herbs for the tzatziki.",
            (
                "Warm the pita and fill it with hummus, sliced chicken, vegetables, "
                "feta, and tzatziki."
            ),
        ),
    ),
    _MealGuide(
        name="Honey-lime salmon, cilantro rice, and broccoli",
        aliases=("honey lime salmon",),
        ingredients=(
            "6 oz salmon; 1 cup cooked rice; 2 cups broccoli; 2 tsp olive oil; "
            "1 lime; 1 tsp honey; garlic; smoked paprika; cilantro"
        ),
        steps=(
            "Heat the oven to 425 F and roast the seasoned broccoli for 10 minutes.",
            "Mix honey, lime juice, garlic, paprika, and oil; brush it over the salmon.",
            "Add the salmon and roast for 10-12 minutes, until it flakes easily.",
            "Stir lime, cilantro, and salt into the rice and serve with the salmon and broccoli.",
        ),
    ),
    _MealGuide(
        name="Spinach-feta omelet with breakfast potatoes",
        aliases=("spinach feta omelet",),
        ingredients=(
            "3 eggs; 1/3 cup egg whites; 2 cups spinach; 1/4 cup feta; tomato; "
            "1 medium potato; fruit"
        ),
        steps=(
            (
                "Dice and microwave the potato for 3-4 minutes, then brown it with "
                "paprika, salt, and pepper."
            ),
            "Remove the potatoes and wilt the spinach in the same skillet.",
            (
                "Add the beaten eggs and whites; add feta and tomato when nearly set, "
                "fold, and cook 1 minute more."
            ),
        ),
    ),
    _MealGuide(
        name="Steak burrito bowl",
        aliases=("steak burrito bowl",),
        ingredients=(
            "5-6 oz sirloin or flank steak; 3/4-1 cup cooked rice; 1/2 cup black beans; "
            "corn; lettuce; salsa; 1/4 avocado; lime; cilantro"
        ),
        steps=(
            "Season the steak with chili powder, cumin, garlic, salt, and pepper.",
            (
                "Sear in a very hot skillet for 3-5 minutes per side; rest for 5 minutes "
                "and slice across the grain."
            ),
            (
                "Build the bowl with rice, beans, corn, lettuce, salsa, avocado, lime, "
                "cilantro, and steak."
            ),
        ),
    ),
    _MealGuide(
        name="Turkey meatballs, spaghetti, and garlic zucchini",
        aliases=("turkey meatballs",),
        ingredients=(
            "7 oz lean ground turkey; 1 egg; 2 tbsp whole-grain breadcrumbs; "
            "1 tbsp Parmesan; Italian seasoning; 2 oz dry whole-wheat spaghetti; "
            "3/4 cup marinara; 1 zucchini"
        ),
        steps=(
            (
                "Heat the oven to 400 F. Mix the turkey, half a beaten egg, breadcrumbs, "
                "Parmesan, garlic, and seasoning; form 5-6 meatballs."
            ),
            "Bake for 15-18 minutes, until the centers reach 165 F.",
            "Boil the pasta and warm the marinara with the meatballs.",
            "Saute sliced zucchini with garlic for 5-6 minutes and serve beside the pasta.",
        ),
    ),
    _MealGuide(
        name="Blueberry oat pancakes with Greek yogurt",
        aliases=("blueberry oat pancakes",),
        ingredients=(
            "1/2 cup rolled oats; 1/2 banana; 2 eggs; 1/2 cup cottage cheese; "
            "1/2 tsp baking powder; cinnamon; blueberries; 1/2 cup Greek yogurt"
        ),
        steps=(
            (
                "Blend the oats, banana, eggs, cottage cheese, baking powder, and "
                "cinnamon until smooth."
            ),
            "Rest the batter for 2 minutes, then cook small pancakes for 2-3 minutes per side.",
            "Top with blueberries and Greek yogurt.",
        ),
    ),
    _MealGuide(
        name="Buffalo chicken loaded baked potato",
        aliases=("buffalo chicken loaded",),
        ingredients=(
            "1 large russet potato; 5 oz chicken breast; buffalo sauce; "
            "2 tbsp shredded cheese; green onion; 2 tbsp Greek yogurt; slaw or salad"
        ),
        steps=(
            (
                "Pierce and microwave the potato for 7-10 minutes; optionally crisp it "
                "at 425 F for 5 minutes."
            ),
            (
                "Dice and season the chicken, cook it for 6-8 minutes until it reaches "
                "165 F, then add buffalo sauce."
            ),
            (
                "Split and fluff the potato; top with chicken, cheese, yogurt, and green "
                "onion and serve with greens."
            ),
        ),
    ),
    _MealGuide(
        name="Shrimp tacos with lime slaw and black beans",
        aliases=("shrimp tacos",),
        ingredients=(
            "7-8 oz peeled shrimp; 3 corn tortillas; 2 cups slaw mix; "
            "1/2 cup black beans; 1/4 avocado; lime; cilantro; Greek yogurt; "
            "chili powder; cumin; garlic; paprika"
        ),
        steps=(
            "Mix the slaw with lime juice, Greek yogurt, cilantro, and salt.",
            "Season the shrimp with chili powder, cumin, garlic, paprika, salt, and pepper.",
            "Saute the shrimp for about 2 minutes per side, until pink and opaque.",
            (
                "Warm the tortillas and fill with slaw, shrimp, avocado, and lime; "
                "serve with warm beans."
            ),
        ),
    ),
    _MealGuide(
        name="Egg, avocado, and turkey-bacon breakfast sandwich",
        aliases=("egg avocado and turkey bacon", "turkey bacon breakfast sandwich"),
        ingredients=(
            "1 whole-grain English muffin or 2 slices whole-grain bread; 2 eggs; "
            "1/3 cup egg whites; 2 slices turkey bacon; 1/4 avocado; tomato; "
            "spinach; hot sauce"
        ),
        steps=(
            "Toast the bread and cook the turkey bacon.",
            "Scramble or fold-cook the eggs and egg whites; wilt the spinach at the end.",
            "Build the sandwich with avocado, tomato, eggs, bacon, and hot sauce.",
        ),
    ),
    _MealGuide(
        name="Homemade turkey burger with oven fries",
        aliases=("turkey burger",),
        ingredients=(
            "6 oz lean ground turkey; 1 whole-grain bun; lettuce; tomato; onion; "
            "pickle; mustard; 1 medium potato; side salad"
        ),
        steps=(
            (
                "Heat the oven to 425 F. Cut and season the potato, then roast for 25-30 "
                "minutes, flipping once."
            ),
            (
                "Form and season the turkey patty; cook for 5-6 minutes per side, until "
                "it reaches 165 F."
            ),
            (
                "Toast the bun, assemble the burger with vegetables and mustard, and "
                "serve with fries and salad."
            ),
        ),
    ),
    _MealGuide(
        name="Chicken fajita skillet with warm tortillas",
        aliases=("chicken fajita skillet",),
        ingredients=(
            "6 oz chicken breast; 1 bell pepper; 1/2 onion; 3 small tortillas; "
            "1/2 cup black beans; 1/4 avocado; salsa; lime; fajita seasoning"
        ),
        steps=(
            (
                "Slice the chicken, pepper, and onion; season with chili powder, cumin, "
                "paprika, garlic, salt, and pepper."
            ),
            (
                "Sear the chicken for 5-6 minutes and remove it; cook the peppers and "
                "onion for 5 minutes."
            ),
            "Return the chicken, add lime, and cook 1 minute more.",
            "Serve with warm tortillas, beans, avocado, and salsa.",
        ),
    ),
    _MealGuide(
        name="Shakshuka with feta and whole-grain toast",
        aliases=("shakshuka",),
        ingredients=(
            "3 eggs; 1 cup crushed tomatoes; 1/2 bell pepper; 1/4 onion; "
            "1/3 cup chickpeas; garlic; cumin; paprika; 2 tbsp feta; "
            "2 slices whole-grain toast"
        ),
        steps=(
            (
                "Saute the onion and pepper for 5 minutes; add garlic, cumin, and paprika "
                "for 30 seconds."
            ),
            "Add tomatoes and chickpeas and simmer for 6-8 minutes.",
            "Make three wells, add the eggs, cover, and cook until the whites set.",
            "Top with feta and serve with toast.",
        ),
    ),
    _MealGuide(
        name="Chicken pesto pasta salad",
        aliases=("chicken pesto pasta salad",),
        ingredients=(
            "5 oz chicken breast; 2 oz dry whole-wheat pasta; 1 tbsp pesto; "
            "cherry tomatoes; cucumber; spinach or arugula; lemon; Parmesan"
        ),
        steps=(
            "Boil the pasta, drain it, and briefly rinse it under cool water.",
            (
                "Season and cook the chicken for 4-5 minutes per side, until it reaches "
                "165 F; rest and slice."
            ),
            (
                "Toss pasta with pesto, lemon, tomatoes, cucumber, greens, and Parmesan; "
                "top with the warm chicken."
            ),
        ),
    ),
    _MealGuide(
        name="Garlic-rosemary sirloin, sweet potato, and asparagus",
        aliases=("garlic rosemary sirloin",),
        ingredients=(
            "6 oz sirloin steak; 1 large sweet potato; 1.5 cups asparagus; "
            "2 tsp olive oil; garlic; rosemary; milk; salt; pepper"
        ),
        steps=(
            (
                "Cube and boil the sweet potato for 12-15 minutes; drain and mash with "
                "milk, salt, and pepper."
            ),
            (
                "Season the steak and sear it in a hot oiled skillet for 3-5 minutes per "
                "side; rest for 5 minutes."
            ),
            "Saute the asparagus with oil, garlic, salt, and pepper for 6-8 minutes.",
            "Slice the steak across the grain and serve with the sweet potato and asparagus.",
        ),
    ),
)


class SemesterOpsService:
    """Shared adapter-facing facade; domain rules stay in focused services."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.schedule = ScheduleService(session)
        self.tracking = TrackingService(session)
        self.imports = ImportService(session)
        self.assignment_study = AssignmentStudyService(session)

    def get_import_schema(self) -> dict[str, Any]:
        schema_path = Path(__file__).resolve().parents[3] / "schemas" / "import-v1.json"
        return cast(dict[str, Any], json.loads(schema_path.read_text(encoding="utf-8")))

    def get_planning_context(self, start_date: date | str, end_date: date | str) -> dict[str, Any]:
        start_day = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
        end_day = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
        if end_day < start_day:
            raise ValueError("end_date must be on or after start_date")
        settings = get_or_create_settings(self.session)
        start_utc, _ = operational_day_bounds(
            start_day, settings.timezone, settings.operational_day_boundary
        )
        _, end_utc = operational_day_bounds(
            end_day, settings.timezone, settings.operational_day_boundary
        )
        blocks = self.schedule.list_occurrences(start_utc, end_utc)
        semester_name = None
        if settings.active_semester_id:
            from semester_ops.db.models import Semester

            active_semester = self.session.get(Semester, settings.active_semester_id)
            semester_name = active_semester.name if active_semester else None
        return {
            "semester_name": semester_name,
            "schedule_revision": settings.schedule_revision,
            "timezone": settings.timezone,
            "start_date": start_day.isoformat(),
            "end_date": end_day.isoformat(),
            "blocks": [self._block_dto(item) for item in blocks],
            "free_windows": self._free_windows(start_utc, end_utc, blocks),
            "assignments": self._assignment_rows(AssignmentInboxStatus.INBOX.value),
        }

    def list_assignment_inbox(self, status: str = "inbox") -> list[dict[str, Any]]:
        return self._assignment_rows(status)

    def create_import_draft(
        self,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
        base_revision: int | None = None,
    ) -> dict[str, Any]:
        draft = self.imports.create_draft(
            payload,
            idempotency_key=idempotency_key,
            base_revision=base_revision,
        )
        self.session.commit()
        return self._draft_dto(draft)

    def create_planning_draft(
        self,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
        base_revision: int | None = None,
    ) -> dict[str, Any]:
        return self.create_import_draft(payload, idempotency_key, base_revision)

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        return self._draft_dto(self.imports.get_draft(draft_id))

    def get_today(self, day: date | str | None = None) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        if day is None:
            local_today = datetime.now(UTC).astimezone(ZoneInfo(settings.timezone)).date()
        else:
            local_today = date.fromisoformat(day) if isinstance(day, str) else day
        blocks = self.schedule.get_today(local_today)
        conflicts = self.schedule.conflicts(blocks)
        conflicted_ids = {
            item_id
            for conflict in conflicts
            for item_id in (conflict.first_occurrence_id, conflict.second_occurrence_id)
        }
        block_rows = [self._block_dto(item) for item in blocks]
        for index, row in enumerate(block_rows):
            previous_end = (
                blocks[index - 1].planned_end_utc
                if index
                else operational_day_bounds(
                    local_today, settings.timezone, settings.operational_day_boundary
                )[0]
            )
            row["gap_before_minutes"] = max(
                0, int((blocks[index].planned_start_utc - previous_end).total_seconds() // 60)
            )
            row["conflict"] = row["id"] in conflicted_ids
        nutrition = self.schedule.nutrition_totals(blocks)
        trackable = [item for item in blocks if item.requires_completion]
        completed = sum(item.status is TrackingStatus.COMPLETED for item in trackable)
        total_sets = sum(
            len(exercise.sets) for block in blocks for exercise in block.workout_exercises
        )
        completed_sets = sum(
            workout_set.completed_at is not None
            for block in blocks
            for exercise in block.workout_exercises
            for workout_set in exercise.sets
        )
        return {
            "selected_date": local_today.isoformat(),
            "date_label": f"{local_today.strftime('%A, %B')} {local_today.day}",
            "previous_date": (local_today - timedelta(days=1)).isoformat(),
            "next_date": (local_today + timedelta(days=1)).isoformat(),
            "timezone": settings.timezone,
            "schedule_revision": settings.schedule_revision,
            "blocks": block_rows,
            "summary": {
                "completed_blocks": completed,
                "trackable_blocks": len(trackable),
                "completion_percent": round(completed / len(trackable) * 100) if trackable else 0,
                "calories_consumed": str(nutrition.consumed_calories),
                "calorie_target": settings.calorie_target or 0,
                "calorie_percent": (
                    min(
                        100,
                        round(float(nutrition.consumed_calories) / settings.calorie_target * 100),
                    )
                    if settings.calorie_target
                    else 0
                ),
                "protein_consumed": str(nutrition.consumed_protein_grams),
                "protein_target": settings.protein_target_grams or 0,
                "workout_sets_completed": completed_sets,
                "workout_sets_total": total_sets,
                "workout_percent": round(completed_sets / total_sets * 100) if total_sets else 0,
                "workout_actual_minutes": sum(
                    int((item.actual_end_utc - item.actual_start_utc).total_seconds() // 60)
                    for item in blocks
                    if item.actual_start_utc
                    and item.actual_end_utc
                    and item.category is BlockCategory.WORKOUT
                ),
            },
            "sync": self._sync_card(),
            "current_block": next((row for row in block_rows if row["is_current"]), None),
            "now_label": datetime.now(UTC)
            .astimezone(ZoneInfo(settings.timezone))
            .strftime("%I:%M %p"),
            "conflicts": [
                {
                    "first_occurrence_id": item.first_occurrence_id,
                    "second_occurrence_id": item.second_occurrence_id,
                    "overlap_start_utc": item.overlap_start_utc.isoformat(),
                    "overlap_end_utc": item.overlap_end_utc.isoformat(),
                }
                for item in conflicts
            ],
        }

    def get_week(self, start: date | str | None = None) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        zone = ZoneInfo(settings.timezone)
        if start is None:
            today = datetime.now(UTC).astimezone(zone).date()
            start_date = today - timedelta(days=today.weekday())
        else:
            start_date = date.fromisoformat(start) if isinstance(start, str) else start
        blocks = self.schedule.get_week(start_date)
        conflicts = self.schedule.conflicts(blocks)
        conflicted_ids = {
            item_id
            for conflict in conflicts
            for item_id in (conflict.first_occurrence_id, conflict.second_occurrence_id)
        }
        days = []
        today = datetime.now(UTC).astimezone(zone).date()
        for offset in range(7):
            current = start_date + timedelta(days=offset)
            rows = [
                self._block_dto(item)
                for item in blocks
                if self._operational_date(
                    item.planned_start_utc,
                    zone=zone,
                    boundary=settings.operational_day_boundary,
                )
                == current
            ]
            for row in rows:
                row["conflict"] = row["id"] in conflicted_ids
            days.append(
                {
                    "date": current.isoformat(),
                    "weekday_short": current.strftime("%a").upper(),
                    "day_number": current.day,
                    "is_today": current == today,
                    "blocks": rows,
                }
            )
        planned_minutes = sum(
            int((item.planned_end_utc - item.planned_start_utc).total_seconds() // 60)
            for item in blocks
        )
        fixed_minutes = sum(
            int((item.planned_end_utc - item.planned_start_utc).total_seconds() // 60)
            for item in blocks
            if item.flexibility is Flexibility.FIXED
        )
        end_date = start_date + timedelta(days=6)
        deadlines = [
            item
            for item in self._assignment_rows()
            if item["due_date"] and start_date <= date.fromisoformat(item["due_date"]) <= end_date
        ]
        return {
            "week_label": (
                f"{start_date.strftime('%B')} {start_date.day} - "
                f"{end_date.strftime('%B')} {end_date.day}"
            ),
            "anchor_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "previous_anchor": (start_date - timedelta(days=7)).isoformat(),
            "next_anchor": (start_date + timedelta(days=7)).isoformat(),
            "days": days,
            "summary": {
                "planned_hours": round(planned_minutes / 60, 1),
                "fixed_hours": round(fixed_minutes / 60, 1),
                "open_hours": round(max(0, 7 * 24 * 60 - planned_minutes) / 60, 1),
                "block_count": len(blocks),
                "conflict_count": len(conflicts),
            },
            "deadlines": deadlines,
        }

    def _assignment_rows(self, state: str | None = None) -> list[dict[str, Any]]:
        statement = (
            select(Assignment)
            .options(
                selectinload(Assignment.course),
                selectinload(Assignment.block_links).selectinload(AssignmentBlockLink.occurrence),
            )
            .order_by(Assignment.due_at_utc, Assignment.due_date, Assignment.title)
        )
        if state:
            statement = statement.where(Assignment.inbox_status == AssignmentInboxStatus(state))
        zone = ZoneInfo(get_or_create_settings(self.session).timezone)
        now = datetime.now(UTC)
        rows: list[dict[str, Any]] = []
        for item in self.session.scalars(statement):
            due_local = item.due_at_utc.astimezone(zone) if item.due_at_utc else None
            due_date = item.due_date or (due_local.date() if due_local else None)
            deadline = item.due_at_utc
            if deadline is None and due_date is not None:
                deadline = resolve_wall_time(due_date, time(23, 59), str(zone)).astimezone(UTC)
            urgency = "normal"
            if deadline is not None:
                if deadline < now:
                    urgency = "overdue"
                elif deadline <= now + timedelta(hours=72):
                    urgency = "soon"
            linked_blocks = [
                {
                    "id": link.occurrence.id,
                    "date_label": link.occurrence.occurrence_date.strftime("%b %d"),
                    "time_label": link.occurrence.planned_start_utc.astimezone(zone).strftime(
                        "%I:%M %p"
                    ),
                    "needs_replanning": link.needs_replanning,
                }
                for link in item.block_links
            ]
            rows.append(
                {
                    "id": item.id,
                    "course_id": item.course_id,
                    "course_code": item.course.code if item.course else None,
                    "course_name": item.course.name if item.course else None,
                    "title": item.title,
                    "due_precision": item.due_precision.value,
                    "due_date": due_date.isoformat() if due_date else None,
                    "due_at_utc": item.due_at_utc.isoformat() if item.due_at_utc else None,
                    "due_day": due_date.strftime("%b %d") if due_date else "TBD",
                    "due_time": due_local.strftime("%I:%M %p") if due_local else "",
                    "due_label": (
                        due_local.strftime("%b %d at %I:%M %p")
                        if due_local
                        else due_date.strftime("%b %d")
                        if due_date
                        else "TBD"
                    ),
                    "urgency": urgency,
                    "url": item.url,
                    "source_url": item.url,
                    "status": item.inbox_status.value,
                    "state": item.inbox_status.value,
                    "source_state": item.source_state.value,
                    "estimated_effort_minutes": item.estimated_effort_minutes,
                    "estimated_minutes": item.estimated_effort_minutes,
                    "linked_block_count": len(linked_blocks),
                    "linked_blocks": linked_blocks,
                    "source_changed": item.source_changed,
                }
            )
        return rows

    def list_assignments(self, state: str | None = None) -> dict[str, Any]:
        rows = self._assignment_rows(state)
        all_rows = self._assignment_rows()
        settings = get_or_create_settings(self.session)
        due_soon = sum(item["urgency"] in {"soon", "overdue"} for item in all_rows)
        blackboard_state = self.session.scalar(
            select(ExternalSourceState)
            .where(ExternalSourceState.connector == SyncConnector.BLACKBOARD)
            .order_by(ExternalSourceState.last_success_at.desc())
        )
        return {
            "assignments": rows,
            "active_state": state,
            "counts": {
                status.value: sum(item["status"] == status.value for item in all_rows)
                for status in AssignmentInboxStatus
            }
            | {"due_soon": due_soon},
            "source": {
                "status": "connected" if settings.blackboard_ics_url else "unconfigured",
                "label": "Connected" if settings.blackboard_ics_url else "Not configured",
                "last_refreshed_at": (
                    blackboard_state.last_success_at.isoformat()
                    if blackboard_state and blackboard_state.last_success_at
                    else None
                ),
            },
        }

    def get_assignment_study(self, assignment_id: str) -> dict[str, Any]:
        return self._assignment_study_view(assignment_id)

    def get_assignment_study_schema(self) -> dict[str, Any]:
        return assignment_study_schema()

    def _assignment_study_view(
        self,
        assignment_id: str,
        quiz_result: QuizResult | None = None,
    ) -> dict[str, Any]:
        assignment = self.assignment_study.get_assignment(assignment_id)
        assignment_row = next(row for row in self._assignment_rows() if row["id"] == assignment_id)
        assignment_row["description"] = assignment.description
        documents = [
            {
                "id": document.id,
                "filename": document.original_filename,
                "media_type": document.media_type,
                "size_bytes": document.size_bytes,
                "page_count": document.page_count,
                "extracted_character_count": document.extracted_character_count,
                "is_truncated": document.is_truncated,
                "created_at": document.created_at.isoformat(),
            }
            for document in assignment.documents
        ]
        study: dict[str, Any] | None = None
        if assignment.study_set is not None:
            questions: list[dict[str, Any]] = []
            for stored_question in assignment.study_set.questions_json:
                question_id = str(stored_question["id"])
                question: dict[str, Any] = {
                    "id": question_id,
                    "prompt": str(stored_question["prompt"]),
                    "choices": [str(choice) for choice in stored_question["choices"]],
                    "source_filename": str(stored_question["source_filename"]),
                }
                if quiz_result is not None:
                    feedback = quiz_result.answers.get(question_id)
                    if feedback is not None:
                        question["feedback"] = feedback
                questions.append(question)
            study = {
                "summary": assignment.study_set.summary,
                "key_points": assignment.study_set.key_points_json,
                "questions": questions,
                "sources": assignment.study_set.source_metadata_json,
                "assumptions": assignment.study_set.assumptions_json,
                "generator": assignment.study_set.generator,
                "generated_at": assignment.study_set.generated_at.isoformat(),
            }
        return {
            "assignment": assignment_row,
            "documents": documents,
            "study": study,
            "quiz_result": (
                {
                    "correct_count": quiz_result.correct_count,
                    "question_count": quiz_result.question_count,
                    "percent": round(quiz_result.correct_count / quiz_result.question_count * 100)
                    if quiz_result.question_count
                    else 0,
                }
                if quiz_result is not None
                else None
            ),
            "nav_path": "/assignments",
        }

    def list_imports(self) -> dict[str, Any]:
        drafts = self.session.scalars(
            select(ImportDraft)
            .options(selectinload(ImportDraft.changes), selectinload(ImportDraft.issues))
            .order_by(ImportDraft.created_at.desc())
        )
        rows = [self._draft_dto(item) for item in drafts]
        return {
            "drafts": rows,
            "counts": {
                "pending": sum(item["status"] in {"ready", "blocked"} for item in rows),
                "applied": sum(item["status"] == "applied" for item in rows),
                "rejected": sum(item["status"] == "rejected" for item in rows),
            },
        }

    def get_import(self, draft_id: str) -> dict[str, Any]:
        draft_model = self.imports.get_draft(draft_id)
        draft = self._draft_dto(draft_model)
        current = get_or_create_settings(self.session).schedule_revision
        draft["current_revision"] = current
        draft["is_stale"] = draft["base_revision"] != current
        return {
            "draft": draft,
            "changes": [self._import_change_view(item) for item in draft["changes"]],
            "issues": draft["issues"],
            "error_count": sum(item["blocking"] for item in draft["issues"]),
            "warning_count": sum(item["severity"] == "warning" for item in draft["issues"]),
            "payload_json": json.dumps(draft_model.payload_json, indent=2, sort_keys=True),
        }

    def set_block_status(self, block_id: str, action: str) -> dict[str, Any]:
        action_to_status = {
            "start": TrackingStatus.IN_PROGRESS,
            "complete": TrackingStatus.COMPLETED,
            "skip": TrackingStatus.SKIPPED,
            "reopen": TrackingStatus.PLANNED,
        }
        status = action_to_status.get(action)
        if status is None:
            status = TrackingStatus(action)
        block = self.tracking.set_status(block_id, status)
        self.session.commit()
        return {"message": f"{block.title} is now {block.status.value}."}

    def get_settings_view(self) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        runtime = get_runtime_settings()
        summary = self.sync_summary()
        source_states = list(self.session.scalars(select(ExternalSourceState)))
        open_conflicts = list(
            self.session.scalars(
                select(SyncConflict)
                .where(SyncConflict.status == SyncConflictStatus.OPEN)
                .order_by(SyncConflict.created_at.desc())
                .limit(20)
            )
        )
        zone = ZoneInfo(settings.timezone)
        conflict_rows: list[dict[str, Any]] = []
        for conflict in open_conflicts:
            occurrence = self.session.get(BlockOccurrence, conflict.occurrence_id)
            if occurrence is None:
                continue
            conflict_rows.append(
                {
                    "id": conflict.id,
                    "occurrence_id": occurrence.id,
                    "title": occurrence.title,
                    "planner_start_local": occurrence.planned_start_utc.astimezone(zone),
                    "planner_end_local": occurrence.planned_end_utc.astimezone(zone),
                    "remote_start_local": conflict.remote_start_utc.astimezone(zone),
                    "remote_end_local": conflict.remote_end_utc.astimezone(zone),
                    "created_at": conflict.created_at,
                }
            )

        def last_success(connector: SyncConnector) -> str:
            values = [
                item.last_success_at
                for item in source_states
                if item.connector is connector and item.last_success_at is not None
            ]
            return max(values).isoformat() if values else "Never"

        google_credentials_present = bool(
            settings.google_calendar_id
            and runtime.google_client_secret_file
            and runtime.google_client_secret_file.is_file()
            and runtime.google_token_file.is_file()
        )
        latest_google_run = next(
            (run for run in summary["runs"] if run["connector"] == SyncConnector.GOOGLE.value),
            None,
        )
        google_continuation = bool(latest_google_run and latest_google_run["continuation_required"])
        google_connector_failed = bool(
            latest_google_run and latest_google_run["status"] == "failed"
        )
        google_retry_required = bool(
            latest_google_run
            and latest_google_run["status"] == "partial"
            and latest_google_run["errors"]
        )
        google_needs_review = bool(
            latest_google_run
            and latest_google_run["status"] == "partial"
            and not google_continuation
            and not google_retry_required
        )

        google_status = "unconfigured"
        google_status_label = "Not configured"
        google_notice: dict[str, Any] | None = None
        if settings.google_calendar_id and not google_credentials_present:
            google_status = "attention"
            google_status_label = "OAuth needed"
            google_notice = {
                "tone": "warning",
                "title": "Authorization required",
                "message": "The local Google authorization files are incomplete.",
                "recovery": _GOOGLE_RECOVERY_BY_CODE["oauth_required"],
                "command": (".\\.venv\\Scripts\\semester-ops-google-setup.exe --reauthorize"),
            }
        elif google_connector_failed and latest_google_run:
            error_code = latest_google_run["error_code"] or "calendar_read_failed"
            google_status = "error"
            google_status_label = "Action required"
            google_notice = {
                "tone": "error",
                "title": error_code.replace("_", " "),
                "message": latest_google_run["message"] or "Google synchronization failed.",
                "recovery": (
                    latest_google_run["recovery"]
                    or _GOOGLE_RECOVERY_BY_CODE.get(
                        error_code,
                        "Review the latest sync and press Sync now again.",
                    )
                ),
                "command": (
                    ".\\.venv\\Scripts\\semester-ops-google-setup.exe --reauthorize"
                    if error_code in {"oauth_required", "oauth_refresh_failed"}
                    else None
                ),
            }
        elif google_retry_required and latest_google_run:
            error_code = latest_google_run["error_code"]
            recovery = latest_google_run["recovery"] or _GOOGLE_RECOVERY_BY_CODE.get(
                error_code or "",
                "Press Sync now again; deterministic IDs prevent duplicates.",
            )
            google_status = (
                "error"
                if error_code
                in {
                    "oauth_required",
                    "oauth_refresh_failed",
                    "calendar_not_found",
                    "calendar_permission_denied",
                }
                else "attention"
            )
            google_status_label = "Retry required"
            deferred = latest_google_run["remote_mutations_deferred"]
            google_notice = {
                "tone": "error" if google_status == "error" else "warning",
                "title": (error_code or "Some calendar changes need retry").replace("_", " "),
                "message": (
                    latest_google_run["message"]
                    or "Google kept the successful changes from the latest bounded batch."
                    + (f" {deferred} additional change(s) remain." if deferred else "")
                ),
                "recovery": recovery,
                "command": (
                    ".\\.venv\\Scripts\\semester-ops-google-setup.exe --reauthorize"
                    if error_code in {"oauth_required", "oauth_refresh_failed"}
                    else None
                ),
            }
        elif google_continuation and latest_google_run:
            deferred = latest_google_run["remote_mutations_deferred"]
            attempted = latest_google_run["remote_mutations_attempted"]
            google_status = "progress"
            google_status_label = "Sync in progress"
            google_notice = {
                "tone": "progress",
                "title": "Bounded calendar bootstrap",
                "message": (
                    f"The latest safe batch attempted {attempted} calendar change(s); "
                    f"{deferred} remain."
                ),
                "recovery": "Press Sync now again to process the next bounded batch.",
                "command": None,
            }
        elif google_needs_review:
            google_status = "attention"
            google_status_label = "Review needed"
        elif google_credentials_present and latest_google_run is None:
            google_status = "progress"
            google_status_label = "Smoke test ready"
            google_notice = {
                "tone": "progress",
                "title": "One-event safety check",
                "message": (
                    "The first successful sync writes at most one Google event so you can "
                    "verify the development calendar."
                ),
                "recovery": "Press Sync now, inspect that event in Google, then continue.",
                "command": None,
            }
        elif google_credentials_present:
            google_status = "connected"
            google_status_label = "Connected"

        return {
            "settings": {
                "timezone": settings.timezone,
                "operational_day_start": settings.operational_day_boundary.strftime("%H:%M"),
                "missed_grace_minutes": settings.missed_grace_minutes,
                "calorie_target": settings.calorie_target,
                "protein_target_grams": settings.protein_target_grams,
                "weight_unit": settings.weight_unit,
                "blackboard_configured": bool(settings.blackboard_ics_url),
            },
            "connectors": [
                {
                    "kind": "GOOGLE",
                    "name": "Semester Ops - Dev",
                    "status": google_status,
                    "status_label": google_status_label,
                    "description": (
                        "Only the app-created development calendar can receive owned events."
                    ),
                    "notice": google_notice,
                    "details": [
                        {
                            "label": "Calendar ID",
                            "value": "Stored locally" if settings.google_calendar_id else "Missing",
                        },
                        {
                            "label": "Last complete sync",
                            "value": last_success(SyncConnector.GOOGLE),
                        },
                        {
                            "label": "Write safety",
                            "value": (
                                f"{runtime.google_initial_sync_write_limit} first / "
                                f"{runtime.google_sync_write_limit} later"
                            ),
                        },
                    ],
                },
                {
                    "kind": "BLACKBOARD",
                    "name": "Assignment feed",
                    "status": "connected" if settings.blackboard_ics_url else "unconfigured",
                    "status_label": (
                        "Configured" if settings.blackboard_ics_url else "Not configured"
                    ),
                    "description": "Private ICS feed; Semester Ops never writes to Blackboard.",
                    "details": [
                        {
                            "label": "Feed URL",
                            "value": "Stored locally" if settings.blackboard_ics_url else "Missing",
                        },
                        {
                            "label": "Last success",
                            "value": last_success(SyncConnector.BLACKBOARD),
                        },
                    ],
                },
            ],
            "sync_runs": [
                {
                    **run,
                    "summary": f"{run['connector'].title()} sync {run['status']}",
                }
                for run in summary["runs"]
            ],
            "sync_conflicts": conflict_rows,
        }

    def get_block(self, block_id: str) -> dict[str, Any]:
        block = self.schedule.get_occurrence(block_id)
        row = self._block_dto(block)
        return {
            "block": row,
            "timezone": get_or_create_settings(self.session).timezone,
            "categories": self._category_options(),
        }

    def get_new_block(self, day: date | None = None) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        zone = ZoneInfo(settings.timezone)
        local_now = datetime.now(UTC).astimezone(zone)
        target_day = day or local_now.date()
        if target_day == local_now.date():
            minutes_until_quarter = (15 - local_now.minute % 15) % 15
            if minutes_until_quarter == 0 and (local_now.second or local_now.microsecond):
                minutes_until_quarter = 15
            start_local = local_now.replace(second=0, microsecond=0) + timedelta(
                minutes=minutes_until_quarter
            )
        else:
            start_local = resolve_wall_time(target_day, time(9), settings.timezone)
        return {
            "block": {
                "title": "",
                "category": BlockCategory.CUSTOM.value,
                "flexibility": Flexibility.FLEXIBLE.value,
                "start_local": start_local,
                "end_local": start_local + timedelta(hours=1),
                "notes": None,
                "project_to_calendar": True,
            },
            "timezone": settings.timezone,
            "categories": self._category_options(),
        }

    def create_block(self, command: Any) -> str:
        occurrence = self.schedule.create_occurrence(
            title=command.title,
            start_utc=self._local_command_time(command.planned_start_local),
            end_utc=self._local_command_time(command.planned_end_local),
            category=BlockCategory(command.category),
            flexibility=Flexibility(command.flexibility),
            notes=command.notes,
            calendar_projection=command.project_to_calendar,
        )
        self.session.commit()
        return occurrence.id

    def duplicate_block(self, block_id: str) -> str:
        occurrence = self.schedule.duplicate_occurrence(block_id)
        self.session.commit()
        return occurrence.id

    def delete_block(self, block_id: str) -> None:
        self.schedule.cancel_occurrence(block_id)
        self.session.commit()

    def update_block(self, block_id: str, command: Any) -> None:
        block = self.schedule.get_occurrence(block_id)
        start = self._local_command_time(command.planned_start_local)
        end = self._local_command_time(command.planned_end_local)
        self.schedule.move_occurrence(block_id, start, end)
        block.title = command.title
        block.category = BlockCategory(command.category)
        block.flexibility = Flexibility(command.flexibility)
        block.notes = command.notes
        block.calendar_projection = command.project_to_calendar
        self.session.commit()

    def move_block(self, block_id: str, minutes: int) -> None:
        if not minutes or minutes % 15:
            raise ValueError("blocks move in non-zero 15-minute increments")
        block = self.schedule.get_occurrence(block_id)
        self.schedule.move_occurrence(
            block_id,
            block.planned_start_utc + timedelta(minutes=minutes),
            block.planned_end_utc + timedelta(minutes=minutes),
        )
        self.session.commit()

    def set_checklist_item(self, item_id: str, *, completed: bool) -> None:
        self.tracking.set_checklist_item_completed(item_id, completed)
        self.session.commit()

    def set_meal_item(self, item_id: str, command: Any) -> None:
        self.tracking.set_meal_item_completed(
            item_id,
            command.completed,
            consumed_quantity=command.consumed_quantity,
        )
        self.session.commit()

    def set_workout_set(self, set_id: str, command: Any) -> None:
        self.tracking.complete_workout_set(
            set_id,
            command.completed,
            actual_reps=command.actual_reps,
            actual_weight=command.actual_weight,
        )
        self.session.commit()

    def set_assignment_state(
        self,
        assignment_id: str,
        *,
        state: str,
        estimated_minutes: int | None,
    ) -> None:
        assignment = self.session.get(Assignment, assignment_id)
        if assignment is None:
            raise NotFoundError(f"assignment {assignment_id} was not found")
        target = AssignmentInboxStatus(state)
        assignment.inbox_status = target
        assignment.estimated_effort_minutes = estimated_minutes
        if target in {
            AssignmentInboxStatus.PLANNED,
            AssignmentInboxStatus.COMPLETED,
            AssignmentInboxStatus.IGNORED,
        }:
            assignment.source_changed = False
            for link in assignment.block_links:
                link.needs_replanning = False
        self.session.commit()

    def upload_assignment_document(self, assignment_id: str, command: Any) -> None:
        self.assignment_study.upload_document(
            assignment_id,
            filename=command.filename,
            media_type=command.media_type,
            content=command.content,
        )
        self.session.commit()

    def get_assignment_document(self, assignment_id: str, document_id: str) -> Any:
        from semester_ops.web.services import AssignmentDocumentDownload

        document = self.assignment_study.get_document(assignment_id, document_id)
        return AssignmentDocumentDownload(
            filename=document.original_filename,
            media_type=document.media_type,
            content=document.content_bytes,
        )

    def regenerate_assignment_study(self, assignment_id: str) -> None:
        self.assignment_study.regenerate(assignment_id)
        self.session.commit()

    def submit_assignment_study_set(
        self,
        assignment_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        result = self.assignment_study.submit_json(
            assignment_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        self.session.commit()
        return {
            "assignment_id": assignment_id,
            "study_set_id": result.study_set.id,
            "status": result.status,
            "payload_digest": result.payload_digest,
            "source_digest": result.source_digest,
            "review_url": f"/assignments/{assignment_id}",
        }

    def check_assignment_quiz(
        self,
        assignment_id: str,
        answers: dict[str, str],
    ) -> dict[str, Any]:
        result = self.assignment_study.check_quiz(assignment_id, answers)
        return self._assignment_study_view(assignment_id, result)

    def approve_import(self, draft_id: str, *, allow_warnings: bool) -> dict[str, Any]:
        result = self.apply_import(draft_id, allow_warnings)
        return {"message": f"Applied {len(result['changes'])} reviewed changes."}

    def reject_import(self, draft_id: str) -> None:
        self.imports.reject_draft(draft_id)
        self.session.commit()

    def update_settings(self, command: Any) -> None:
        if command.timezone != "America/Chicago":
            raise ValueError("v1 supports America/Chicago only")
        boundary = time.fromisoformat(command.operational_day_start)
        settings = get_or_create_settings(self.session)
        next_blackboard_url = settings.blackboard_ics_url
        if command.clear_blackboard_ics:
            next_blackboard_url = None
        elif command.blackboard_ics_url:
            validate_blackboard_feed_url(command.blackboard_ics_url)
            next_blackboard_url = command.blackboard_ics_url

        settings.timezone = command.timezone
        settings.operational_day_boundary = boundary
        settings.missed_grace_minutes = command.missed_grace_minutes
        settings.calorie_target = command.calorie_target
        settings.protein_target_grams = command.protein_target_grams
        settings.weight_unit = command.weight_unit
        if next_blackboard_url != settings.blackboard_ics_url:
            settings.blackboard_ics_url = next_blackboard_url
            blackboard_states = self.session.scalars(
                select(ExternalSourceState).where(
                    ExternalSourceState.connector == SyncConnector.BLACKBOARD
                )
            )
            for state in blackboard_states:
                state.etag = None
                state.last_modified = None
        settings.updated_at = utc_now()
        self.session.commit()

    def sync_now(self) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        if not settings.google_calendar_id and not settings.blackboard_ics_url:
            return {
                "tone": "warning",
                "message": "Configure Google Calendar or Blackboard before synchronizing.",
            }
        runtime = get_runtime_settings()
        synchronizers: list[ConnectorSynchronizer] = []
        if settings.blackboard_ics_url:
            synchronizers.append(BlackboardAssignmentSync(BlackboardFeedClient()))
        if settings.google_calendar_id:

            def google_gateway() -> GoogleCalendarGateway:
                if runtime.google_client_secret_file is None:
                    raise GoogleCalendarConfigurationError(
                        "Run the explicit Google setup command before synchronizing"
                    )
                if not runtime.google_token_file.is_file():
                    raise GoogleCalendarConfigurationError(
                        "Run the explicit Google setup command before synchronizing"
                    )
                return GoogleCalendarGateway.from_oauth_files(
                    client_secret_file=runtime.google_client_secret_file,
                    token_file=runtime.google_token_file,
                )

            synchronizers.append(
                GoogleCalendarProjectionSync(
                    google_gateway,
                    remote_mutation_limit=runtime.google_sync_write_limit,
                    initial_remote_mutation_limit=runtime.google_initial_sync_write_limit,
                )
            )

        self.session.commit()
        factory = sessionmaker(
            bind=self.session.get_bind(),
            expire_on_commit=False,
            class_=Session,
        )
        batch = SyncService(factory, synchronizers).sync_now()
        succeeded = sum(run.status.value == "succeeded" for run in batch.runs)
        needs_attention = len(batch.runs) - succeeded
        google_run = next(
            (run for run in batch.runs if run.connector is SyncConnector.GOOGLE),
            None,
        )
        if google_run and google_run.status.value == "failed":
            safe_message = _sync_detail_text(google_run.details.get("message"))
            safe_recovery = _sync_detail_text(google_run.details.get("recovery"))
            error_code = _sync_detail_text(google_run.details.get("error_code"))
            message = safe_message or "Google Calendar synchronization failed."
            recovery = safe_recovery or _GOOGLE_RECOVERY_BY_CODE.get(error_code or "", "")
            if recovery:
                message = f"{message} {recovery}"
            tone = "error"
        elif google_run and google_run.error_count:
            safe_message = _sync_detail_text(google_run.details.get("message"))
            safe_recovery = _sync_detail_text(google_run.details.get("recovery"))
            error_code = _sync_detail_text(google_run.details.get("error_code"))
            message = safe_message or (
                "Google synchronized other calendar changes, but one or more items need a retry."
            )
            recovery = safe_recovery or _GOOGLE_RECOVERY_BY_CODE.get(error_code or "", "")
            if recovery:
                message = f"{message} {recovery}"
            tone = (
                "error"
                if error_code
                in {
                    "oauth_required",
                    "oauth_refresh_failed",
                    "calendar_not_found",
                    "calendar_permission_denied",
                }
                else "warning"
            )
        elif google_run and bool(google_run.details.get("continuation_required")):
            attempted = _sync_detail_count(google_run.details.get("remote_mutations_attempted"))
            deferred = _sync_detail_count(google_run.details.get("remote_mutations_deferred"))
            message = (
                f"Google calendar batch complete: {attempted} change(s) attempted; "
                f"{deferred} remain. Press Sync now again."
            )
            tone = "neutral"
        elif batch.succeeded:
            message = f"Synchronization complete: {succeeded} connector(s) succeeded."
            tone = "success"
        else:
            message = (
                "Synchronization finished with attention: "
                f"{succeeded} succeeded, {needs_attention} need review."
            )
            tone = "warning"
        return {"tone": tone, "message": message, **batch.as_dict()}

    def resolve_sync_conflict(self, conflict_id: str, resolution: str) -> dict[str, str]:
        try:
            resolved_status = SyncConflictStatus(resolution)
        except ValueError as exc:
            raise ValidationError("choose Keep planner or Use Google time") from exc
        if resolved_status is SyncConflictStatus.OPEN:
            raise ValidationError("an open conflict requires a resolution")

        conflict = self.session.get(SyncConflict, conflict_id)
        if conflict is None:
            raise NotFoundError(f"sync conflict {conflict_id} was not found")
        if conflict.status is not SyncConflictStatus.OPEN:
            if conflict.status is resolved_status:
                return {"message": "That calendar conflict was already resolved."}
            raise ValidationError("that calendar conflict has already been resolved")

        occurrence = self.session.get(BlockOccurrence, conflict.occurrence_id)
        if occurrence is None:
            raise NotFoundError(f"block occurrence {conflict.occurrence_id} was not found")
        if resolved_status is SyncConflictStatus.USE_REMOTE:
            self.schedule.move_occurrence(
                occurrence.id,
                conflict.remote_start_utc,
                conflict.remote_end_utc,
                actor="google-conflict-resolution",
            )
            occurrence.override_reason = "Accepted Google Calendar time"
        elif occurrence.calendar_link is not None:
            # Treat the observed remote range as the new base so the next sync sees
            # only the chosen planner range as changed and pushes it to Google.
            occurrence.calendar_link.last_synced_start_utc = conflict.remote_start_utc
            occurrence.calendar_link.last_synced_end_utc = conflict.remote_end_utc

        conflict.status = resolved_status
        conflict.resolved_at = utc_now()
        add_audit_event(
            self.session,
            event_type="calendar.conflict_resolved",
            entity_type="sync_conflict",
            entity_id=conflict.id,
            data={"resolution": resolved_status.value, "occurrence_id": occurrence.id},
        )
        self.session.commit()
        choice = (
            "Google time" if resolved_status is SyncConflictStatus.USE_REMOTE else "planner time"
        )
        return {"message": f"Conflict resolved with {choice}. Sync again to reconcile Google."}

    def toggle_checklist(self, item_id: str, completed: bool | None = None) -> dict[str, Any]:
        item = self.session.get(ChecklistItem, item_id)
        if item is None:
            raise NotFoundError(f"checklist item {item_id} was not found")
        resolved = item.completed_at is None if completed is None else completed
        item = self.tracking.set_checklist_item_completed(item_id, resolved)
        self.session.commit()
        return {
            "id": item.id,
            "completed": item.completed_at is not None,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        }

    def apply_import(self, draft_id: str, allow_warnings: bool = False) -> dict[str, Any]:
        draft = self.imports.apply_draft(draft_id, allow_warnings=allow_warnings)
        self.session.commit()
        return self._draft_dto(draft)

    def sync_summary(self) -> dict[str, Any]:
        latest = self.session.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(20))
        open_conflicts = self.session.scalar(
            select(func.count(SyncConflict.id)).where(
                SyncConflict.status == SyncConflictStatus.OPEN
            )
        )
        return {
            "runs": [self._sync_run_dto(run) for run in latest],
            "open_conflicts": open_conflicts or 0,
        }

    @staticmethod
    def _sync_run_dto(run: SyncRun) -> dict[str, Any]:
        details = run.details_json or {}
        duration_ms = (
            max(0, int((run.finished_at - run.started_at).total_seconds() * 1000))
            if run.finished_at
            else None
        )
        duration_label = (
            "Running"
            if duration_ms is None
            else f"{duration_ms / 1000:.1f}s"
            if duration_ms >= 1000
            else f"{duration_ms}ms"
        )
        return {
            "id": run.id,
            "connector": run.connector.value,
            "status": run.status.value,
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "duration_ms": duration_ms,
            "duration_label": duration_label,
            "created": run.created_count,
            "updated": run.updated_count,
            "deleted": run.deleted_count,
            "conflicts": run.conflict_count,
            "errors": run.error_count,
            "error_code": _sync_detail_text(details.get("error_code")),
            "message": _sync_detail_text(details.get("message")),
            "recovery": _sync_detail_text(details.get("recovery")),
            "category": _sync_detail_text(details.get("category")),
            "continuation_required": bool(details.get("continuation_required")),
            "retry_required": bool(details.get("retry_required")),
            "remote_mutations_attempted": _sync_detail_count(
                details.get("remote_mutations_attempted")
            ),
            "remote_mutations_deferred": _sync_detail_count(
                details.get("remote_mutations_deferred")
            ),
        }

    def _block_dto(self, block: BlockOccurrence) -> dict[str, Any]:
        settings = get_or_create_settings(self.session)
        zone = ZoneInfo(settings.timezone)
        start_local = block.planned_start_utc.astimezone(zone)
        end_local = block.planned_end_utc.astimezone(zone)
        now = datetime.now(UTC)
        status = effective_status(
            block.status,
            planned_end_utc=block.planned_end_utc,
            now_utc=now,
            requires_completion=block.requires_completion,
            grace_minutes=settings.missed_grace_minutes,
        )
        planned_calories, planned_protein = block.planned_nutrition()
        consumed_calories, consumed_protein = block.consumed_nutrition()
        meal_guide = _meal_guide(block)
        workout_exercises: list[dict[str, Any]] = [
            {
                "id": exercise.id,
                "name": exercise.name,
                "planned_sets": exercise.planned_sets,
                "completed_sets": sum(item.completed_at is not None for item in exercise.sets),
                "rep_target": (
                    f"{exercise.rep_min}-{exercise.rep_max} reps"
                    if exercise.rep_min is not None and exercise.rep_max is not None
                    else f"{exercise.rep_min or exercise.rep_max} reps"
                    if exercise.rep_min is not None or exercise.rep_max is not None
                    else ""
                ),
                "target_weight": (
                    str(exercise.target_weight) if exercise.target_weight is not None else None
                ),
                "weight_unit": exercise.weight_unit,
                "notes": exercise.notes,
                "sets": [
                    {
                        "id": workout_set.id,
                        "set_number": workout_set.set_number,
                        "target_reps": workout_set.target_reps,
                        "completed": workout_set.completed_at is not None,
                        "actual_reps": workout_set.actual_reps,
                        "actual_weight": (
                            str(workout_set.actual_weight)
                            if workout_set.actual_weight is not None
                            else None
                        ),
                    }
                    for workout_set in exercise.sets
                ],
            }
            for exercise in block.workout_exercises
        ]
        meal_items = [
            {
                "id": item.id,
                "name": item.food_name,
                "unit": item.unit,
                "planned_quantity": str(item.planned_quantity),
                "consumed_quantity": (
                    str(item.consumed_quantity) if item.consumed_quantity is not None else None
                ),
                "calories": str(item.calories_per_unit * item.planned_quantity),
                "protein_grams": str(item.protein_grams_per_unit * item.planned_quantity),
                "required": item.required,
                "completed": item.completed_at is not None,
            }
            for item in block.meal_items
        ]
        return {
            "id": block.id,
            "title": block.title,
            "category": block.category.value,
            "flexibility": block.flexibility.value,
            "planned_start_utc": block.planned_start_utc.isoformat(),
            "planned_end_utc": block.planned_end_utc.isoformat(),
            "start_local": start_local,
            "end_local": end_local,
            "duration_minutes": int(
                (block.planned_end_utc - block.planned_start_utc).total_seconds() // 60
            ),
            "actual_start_utc": (
                block.actual_start_utc.isoformat() if block.actual_start_utc else None
            ),
            "actual_end_utc": block.actual_end_utc.isoformat() if block.actual_end_utc else None,
            "status": status.value,
            "persisted_status": block.status.value,
            "notes": block.notes,
            "source_notes": block.description,
            "location": block.location,
            "status_label": status.value.replace("_", " ").title(),
            "category_label": block.category.value.replace("_", " ").title(),
            "is_current": block.planned_start_utc <= now < block.planned_end_utc,
            "remaining_minutes": max(0, int((block.planned_end_utc - now).total_seconds() // 60)),
            "conflict": False,
            "unsynced": block.calendar_projection
            and block.cancelled_at is None
            and (
                block.calendar_link is None
                or block.calendar_link.last_synced_local_revision < block.revision
            ),
            "calendar_event_id": block.calendar_link.event_id if block.calendar_link else None,
            "project_to_calendar": block.calendar_projection,
            "actual_start_local": (
                block.actual_start_utc.astimezone(zone) if block.actual_start_utc else None
            ),
            "actual_end_local": (
                block.actual_end_utc.astimezone(zone) if block.actual_end_utc else None
            ),
            "requires_completion": block.requires_completion,
            "calendar_projection": block.calendar_projection,
            "revision": block.revision,
            "checklist_items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "label": item.title,
                    "required": item.required,
                    "completed": item.completed_at is not None,
                }
                for item in block.checklist_items
            ],
            "nutrition": {
                "planned_calories": str(planned_calories),
                "planned_protein_grams": str(planned_protein),
                "consumed_calories": str(consumed_calories),
                "consumed_protein_grams": str(consumed_protein),
            },
            "meal_items": meal_items,
            "meal_guide": meal_guide,
            "meal_summary": {
                "planned_calories": str(planned_calories),
                "consumed_calories": str(consumed_calories),
            },
            "workout_exercises": workout_exercises,
            "workout_guidance": (
                _workout_recovery_guidance(block.description)
                if block.workout_exercises or block.category is BlockCategory.WORKOUT
                else []
            ),
            "workout_summary": {
                "completed_sets": sum(
                    workout_set.completed_at is not None
                    for exercise in block.workout_exercises
                    for workout_set in exercise.sets
                ),
                "total_sets": sum(len(exercise.sets) for exercise in block.workout_exercises),
            },
        }

    @staticmethod
    def _draft_dto(draft: ImportDraft) -> dict[str, Any]:
        payload = draft.payload_json
        semester = payload.get("semester") or {}
        source = payload.get("source") or {}
        title = semester.get("name") or source.get("filename") or "Review proposed changes"
        add_count = sum(item.operation.value == "add" for item in draft.changes)
        cancel_count = sum(item.operation.value in {"cancel", "delete"} for item in draft.changes)
        change_count = len(draft.changes) - add_count - cancel_count
        error_count = sum(item.blocking for item in draft.issues)
        return {
            "id": draft.id,
            "schema_version": draft.schema_version,
            "status": draft.status.value,
            "mode": draft.mode.value,
            "managed_dataset": draft.managed_dataset,
            "title": title,
            "base_revision": draft.base_revision,
            "idempotency_key": draft.idempotency_key,
            "payload_hash": draft.payload_hash,
            "source_filename": draft.source_filename,
            "source_media_type": draft.source_media_type,
            "source_hash": draft.source_sha256,
            "assumptions": draft.assumptions,
            "start_date": draft.scope_start_date.isoformat(),
            "end_date": draft.scope_end_date.isoformat(),
            "scope_label": (
                f"{draft.scope_start_date.strftime('%b')} {draft.scope_start_date.day} - "
                f"{draft.scope_end_date.strftime('%b')} {draft.scope_end_date.day}"
            ),
            "scope": {
                "start_date": draft.scope_start_date.isoformat(),
                "end_date": draft.scope_end_date.isoformat(),
            },
            "created_at": draft.created_at.isoformat(),
            "applied_at": draft.applied_at.isoformat() if draft.applied_at else None,
            "add_count": add_count,
            "change_count": change_count,
            "cancel_count": cancel_count,
            "error_count": error_count,
            "changes": [
                {
                    "id": item.id,
                    "operation": item.operation.value,
                    "entity_type": item.entity_type.value,
                    "target_id": item.target_id,
                    "before": item.before_json,
                    "after": item.after_json,
                }
                for item in draft.changes
            ],
            "issues": [
                {
                    "severity": item.severity.value,
                    "code": item.code,
                    "message": item.message,
                    "path": item.path,
                    "blocking": item.blocking,
                }
                for item in draft.issues
            ],
            "review_url": f"/imports/{draft.id}",
        }

    def _import_change_view(self, change: dict[str, Any]) -> dict[str, Any]:
        value = change.get("after") or change.get("before") or {}
        if not isinstance(value, dict):
            value = {}
        settings = get_or_create_settings(self.session)
        zone = ZoneInfo(settings.timezone)
        start_local: datetime | str | None = value.get("planned_start_utc")
        end_local: datetime | str | None = value.get("planned_end_utc")
        if isinstance(start_local, str):
            start_local = datetime.fromisoformat(start_local).astimezone(zone)
        if isinstance(end_local, str):
            end_local = datetime.fromisoformat(end_local).astimezone(zone)
        occurrence_date = value.get("occurrence_date") or value.get("effective_start_date")
        entity_type = str(change.get("entity_type", "record"))
        title = value.get("title") or value.get("name") or entity_type.replace("_", " ").title()
        return {
            **change,
            "title": title,
            "category": value.get("category", entity_type),
            "flexibility": value.get("flexibility", "fixed"),
            "date_label": occurrence_date or "",
            "start_local": start_local or value.get("start_time"),
            "end_local": end_local,
            "before": self._change_summary(change.get("before")),
            "after": self._change_summary(change.get("after")),
        }

    @staticmethod
    def _change_summary(value: object) -> str | None:
        if not isinstance(value, dict):
            return None
        title = value.get("title") or value.get("name")
        start = value.get("start_time") or value.get("planned_start_utc")
        parts = [str(item) for item in (title, start) if item]
        return " / ".join(parts) if parts else "Record details changed"

    @staticmethod
    def _category_options() -> list[dict[str, str]]:
        return [
            {"value": category.value, "label": category.value.replace("_", " ").title()}
            for category in BlockCategory
        ]

    @staticmethod
    def _free_windows(
        start_utc: datetime,
        end_utc: datetime,
        blocks: list[BlockOccurrence],
    ) -> list[dict[str, str]]:
        cursor = start_utc
        windows: list[dict[str, str]] = []
        for block in sorted(blocks, key=lambda item: item.planned_start_utc):
            if block.planned_start_utc > cursor:
                windows.append(
                    {
                        "start_utc": cursor.isoformat(),
                        "end_utc": block.planned_start_utc.isoformat(),
                    }
                )
            cursor = max(cursor, block.planned_end_utc)
        if cursor < end_utc:
            windows.append({"start_utc": cursor.isoformat(), "end_utc": end_utc.isoformat()})
        return windows

    @staticmethod
    def _local_command_time(value: datetime) -> datetime:
        if value.tzinfo is not None and value.utcoffset() is not None:
            return value.astimezone(UTC)
        return resolve_wall_time(value.date(), value.time(), "America/Chicago").astimezone(UTC)

    @staticmethod
    def _operational_date(value: datetime, *, zone: ZoneInfo, boundary: time) -> date:
        local_value = value.astimezone(zone)
        if local_value.time() < boundary:
            return local_value.date() - timedelta(days=1)
        return local_value.date()

    def _sync_card(self) -> dict[str, Any]:
        last_success = self.session.scalar(
            select(SyncRun)
            .where(SyncRun.status.in_(["succeeded", "partial"]))
            .order_by(SyncRun.finished_at.desc())
            .limit(1)
        )
        dirty = self.session.scalar(
            select(func.count(BlockOccurrence.id))
            .outerjoin(
                CalendarEventLink,
                CalendarEventLink.occurrence_id == BlockOccurrence.id,
            )
            .where(
                BlockOccurrence.cancelled_at.is_(None),
                BlockOccurrence.calendar_projection.is_(True),
                or_(
                    CalendarEventLink.id.is_(None),
                    CalendarEventLink.last_synced_local_revision < BlockOccurrence.revision,
                ),
            )
        )
        return {
            "dirty_count": dirty or 0,
            "last_success_at": (
                last_success.finished_at if last_success and last_success.finished_at else None
            ),
        }


def _sync_detail_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized[:500] or None


def _sync_detail_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _meal_guide(block: BlockOccurrence) -> dict[str, Any] | None:
    if block.category is not BlockCategory.MEAL and not block.meal_items:
        return None

    detail_text = "\n".join(
        value.strip() for value in (block.description, block.notes) if value and value.strip()
    )
    guide = _find_meal_guide(block, detail_text)
    stored_ingredients = _extract_ingredients(block.description or "") or _extract_ingredients(
        block.notes or ""
    )
    stored_steps = _extract_recipe_steps(block.description or "") or _extract_recipe_steps(
        block.notes or ""
    )
    ingredients = stored_ingredients or (
        _split_detail_items(guide.ingredients) if guide is not None else []
    )
    steps = stored_steps or (list(guide.steps) if guide is not None else [])
    uses_guide_fallback = guide is not None and (not stored_ingredients or not stored_steps)

    missing_message: str | None = None
    if not ingredients and not steps:
        missing_message = (
            "This meal has tracked servings, but its source did not include ingredients "
            "or preparation steps."
            if block.meal_items
            else "No ingredient list or preparation steps are stored for this meal block."
        )
    elif not ingredients:
        missing_message = "Preparation steps are available, but no ingredient list is stored."
    elif not steps:
        missing_message = "Ingredients are available, but no preparation steps are stored."

    recipe_name = (
        guide.name
        if guide is not None
        else block.meal_items[0].food_name
        if block.meal_items
        else block.title
    )
    return {
        "name": recipe_name,
        "ingredients": ingredients,
        "steps": steps,
        "source_label": (
            "Stored details + source recipe"
            if (stored_ingredients or stored_steps) and uses_guide_fallback
            else "Stored block details"
            if stored_ingredients or stored_steps
            else "Fresh 7-day source plan"
            if guide is not None
            else None
        ),
        "missing_message": missing_message,
    }


def _find_meal_guide(block: BlockOccurrence, detail_text: str) -> _MealGuide | None:
    identity = _normalize_meal_lookup(
        " ".join([block.title, detail_text, *(item.food_name for item in block.meal_items)])
    )
    for guide in _MEAL_GUIDES:
        if any(_normalize_meal_lookup(alias) in identity for alias in guide.aliases):
            return guide
    return None


def _normalize_meal_lookup(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).split())


def _extract_ingredients(value: str) -> list[str]:
    match = re.search(r"(?is)\bingredients?\s*:\s*(.+)", value)
    if match is None:
        return []
    section = re.split(
        r"(?is)\b(?:tutorial|directions|instructions|method|steps|untimed snack|estimated day)\s*:",
        match.group(1),
        maxsplit=1,
    )[0]
    return _split_detail_items(section)


def _extract_recipe_steps(value: str) -> list[str]:
    match = re.search(
        r"(?is)\b(?:tutorial|directions|instructions|method|steps)\s*:\s*(.+)",
        value,
    )
    if match is None:
        return []
    section = re.split(
        r"(?is)\b(?:ingredients|untimed snack|estimated day)\s*:",
        match.group(1),
        maxsplit=1,
    )[0].strip()
    numbered = re.findall(
        r"(?:^|\n)\s*\d+[.)]\s*(.+?)(?=(?:\n\s*\d+[.)])|\Z)",
        section,
        flags=re.DOTALL,
    )
    raw_steps = numbered or re.split(r"\s*;\s*", section)
    return [cleaned for item in raw_steps if (cleaned := _clean_detail_item(item))][:12]


def _split_detail_items(value: str) -> list[str]:
    return [
        cleaned
        for item in re.split(r"\s*;\s*", value.strip().rstrip("."))
        if (cleaned := _clean_detail_item(item))
    ][:30]


def _clean_detail_item(value: str) -> str:
    return " ".join(value.strip().strip("- ").split()).rstrip(".")


def _workout_recovery_guidance(source_notes: str | None) -> list[dict[str, str]]:
    source = " ".join(source_notes.split()) if source_notes else ""
    warm_up = _source_clause(source, "warm up") or "Warm up for 5-8 minutes"
    effort = _source_clause(source, "leave") or "Leave 2-3 good repetitions in reserve"
    rest = _source_clause(source, "rest") or (
        "Rest 2-3 minutes for compound lifts and 60-90 seconds for smaller exercises"
    )
    return [
        {
            "label": "Before",
            "text": (
                f"{_sentence_text(warm_up)}; use lighter ramp-up sets for the first major lift."
            ),
        },
        {
            "label": "Between sets",
            "text": f"{_sentence_text(effort)}. {_sentence_text(rest)}.",
        },
        {
            "label": "After",
            "text": (
                "Cool down, rehydrate, and use the next normal meal to keep daily protein "
                "on target; prioritize sleep."
            ),
        },
    ]


def _source_clause(value: str, prefix: str) -> str | None:
    if not value:
        return None
    match = re.search(rf"(?i)(?:^|[.;]\s*)({re.escape(prefix)}[^;.]+)", value)
    return _clean_detail_item(match.group(1)) if match else None


def _sentence_text(value: str) -> str:
    return value[:1].upper() + value[1:].rstrip(".")
