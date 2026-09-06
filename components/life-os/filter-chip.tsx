import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function FilterChip({
  active,
  onClick,
  children,
  disabled = false,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <Button
      variant={active ? "default" : "outline"}
      size="sm"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "rounded-full px-3",
        !active && "bg-background/80 text-muted-foreground",
        disabled && "opacity-60",
      )}
    >
      {children}
    </Button>
  );
}
