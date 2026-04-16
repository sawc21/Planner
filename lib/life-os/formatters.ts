import {
  format,
  formatDistanceToNowStrict,
  isToday,
  isTomorrow,
  parseISO,
} from "date-fns";

export function formatItemDateTime(dateValue?: string) {
  if (!dateValue) {
    return "No date";
  }

  const date = parseISO(dateValue);

  if (isToday(date)) {
    return `Today at ${format(date, "h:mm a")}`;
  }

  if (isTomorrow(date)) {
    return `Tomorrow at ${format(date, "h:mm a")}`;
  }

  return format(date, "EEE, MMM d 'at' h:mm a");
}

export function formatItemDay(dateValue?: string) {
  if (!dateValue) {
    return "No date";
  }

  const date = parseISO(dateValue);

  if (isToday(date)) {
    return "Today";
  }

  if (isTomorrow(date)) {
    return "Tomorrow";
  }

  return format(date, "EEEE, MMM d");
}

export function formatDeadlineDistance(dateValue?: string) {
  if (!dateValue) {
    return "No timing";
  }

  return formatDistanceToNowStrict(parseISO(dateValue), { addSuffix: true });
}

export function formatAmount(amount?: number) {
  if (amount == null) {
    return undefined;
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatEstimatedMinutes(item: { estimatedMinutes?: number }) {
  if (!item.estimatedMinutes) {
    return "Flexible";
  }

  if (item.estimatedMinutes < 60) {
    return `${item.estimatedMinutes} min`;
  }

  const hours = Math.floor(item.estimatedMinutes / 60);
  const minutes = item.estimatedMinutes % 60;

  if (!minutes) {
    return `${hours} hr`;
  }

  return `${hours} hr ${minutes} min`;
}
