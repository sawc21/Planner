"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CommandConsole } from "@/components/life-os/command-console";
import { useLifeOs } from "@/lib/life-os/state";

export function CommandPanel() {
  const { commandPanelOpen, closeCommandPanel, clearCommandResult } = useLifeOs();

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      closeCommandPanel();
      clearCommandResult();
    }
  };

  return (
    <Dialog open={commandPanelOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl gap-4 border-white/10 bg-background/96">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold tracking-tight">Quick Orbit command</DialogTitle>
          <DialogDescription>
            Use this modal for quick capture or a one-off action. The full workbench lives on `/assistant`.
          </DialogDescription>
        </DialogHeader>
        <CommandConsole onComplete={() => handleOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
