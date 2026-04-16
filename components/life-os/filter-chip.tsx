import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Button
      variant={active ? "default" : "outline"}
      size="sm"
      onClick={onClick}
      className={cn(
        "rounded-full px-3",
        !active && "bg-background/80 text-muted-foreground",
      )}
    >
      {children}
    </Button>
  );
}
