"""Parsing and next-run computation for scheduled work."""

from datetime import datetime, timedelta, timezone

_CRON_ALIASES = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}

_RELATIVE_UNITS = {
    "s": "seconds",
    "m": "minutes",
    "h": "hours",
    "d": "days",
    "w": "weeks",
}


def _parse_field(field: str, lo: int, hi: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            raise ValueError("empty cron field")
        step = 1
        if "/" in part:
            base, step_s = part.split("/", 1)
            step = int(step_s)
            if step <= 0:
                raise ValueError("invalid step")
        else:
            base = part
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, b = base.split("-", 1)
            start, end = int(a), int(b)
        else:
            if base == "*":
                start, end = lo, hi
            else:
                start = end = int(base)
        if start < lo or end > hi or start > end:
            raise ValueError("cron field out of range")
        for v in range(start, end + 1, step):
            values.add(v)
    if not values:
        raise ValueError("empty cron field")
    return values


def _parse_cron(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError("cron expression must have 5 fields")
    minute = _parse_field(fields[0], 0, 59)
    hour = _parse_field(fields[1], 0, 23)
    dom = _parse_field(fields[2], 1, 31)
    month = _parse_field(fields[3], 1, 12)
    dow = _parse_field(fields[4], 0, 6)
    return minute, hour, dom, month, dow


def _cron_matches(dt: datetime, parsed) -> bool:
    minute, hour, dom, month, dow = parsed
    # python weekday: Monday=0..Sunday=6; cron dow: Sunday=0
    cron_dow = (dt.weekday() + 1) % 7
    return (
        dt.minute in minute
        and dt.hour in hour
        and dt.day in dom
        and dt.month in month
        and cron_dow in dow
    )


def _parse_relative(expr: str) -> timedelta:
    # +1h, +30m, +1d, +2w, +45s, +1h30m
    body = expr[1:]
    total = timedelta()
    i = 0
    num = ""
    while i < len(body):
        ch = body[i]
        if ch.isdigit():
            num += ch
            i += 1
            continue
        if ch in _RELATIVE_UNITS and num:
            n = int(num)
            if ch == "s":
                total += timedelta(seconds=n)
            elif ch == "m":
                total += timedelta(minutes=n)
            elif ch == "h":
                total += timedelta(hours=n)
            elif ch == "d":
                total += timedelta(days=n)
            elif ch == "w":
                total += timedelta(weeks=n)
            num = ""
            i += 1
            continue
        raise ValueError("invalid relative schedule expression")
    if num:
        raise ValueError("invalid relative schedule expression")
    if total == timedelta():
        raise ValueError("invalid relative schedule expression")
    return total


def compute_next_run(expression: str, now: datetime | None = None) -> datetime:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    expr = expression.strip()
    if expr in _CRON_ALIASES:
        expr = _CRON_ALIASES[expr]
    if expr.startswith("+"):
        return now + _parse_relative(expr)
    # ISO timestamp
    try:
        dt = datetime.fromisoformat(expr.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt <= now:
            raise ValueError("schedule time is in the past")
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    # cron
    parsed = _parse_cron(expr)
    candidate = now.replace(second=0, microsecond=0, tzinfo=timezone.utc) + timedelta(minutes=1)
    limit = now + timedelta(days=366)
    while candidate <= limit:
        if _cron_matches(candidate, parsed):
            return candidate.astimezone(timezone.utc)
        candidate += timedelta(minutes=1)
    raise ValueError("no upcoming run for schedule expression")


def validate_schedule_expression(expression: str) -> None:
    compute_next_run(expression)


def is_due(expression: str, last_run: datetime | None = None, now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)
    try:
        nxt = compute_next_run(expression, now=last_run or (now - timedelta(seconds=1)))
    except ValueError:
        return False
    return nxt <= now
