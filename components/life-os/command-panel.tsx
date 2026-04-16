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
  const {
    commandPanelOpen,
    closeCommandPanel,
    clearCommandResult,
  } = useLifeOs();

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      closeCommandPanel();
      clearCommandResult();
    }
  };

  return (
    <Dialog open={commandPanelOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-3xl gap-5">
        <DialogHeader>
          <DialogTitle className="text-2xl font-semibold tracking-tight">Command</DialogTitle>
          <DialogDescription>
            A bounded local command layer for capturing work and generating a plan without turning
            the app into chat.
          </DialogDescription>
        </DialogHeader>
        <CommandConsole onComplete={() => handleOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
