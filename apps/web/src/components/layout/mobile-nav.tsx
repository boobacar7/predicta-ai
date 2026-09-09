"use client";

import { Sidebar } from "@/components/layout/sidebar";
import * as Dialog from "@radix-ui/react-dialog";

export function MobileNav({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 lg:hidden" />
        <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-[min(20rem,90vw)] bg-background lg:hidden">
          <Dialog.Title className="sr-only">Navigation</Dialog.Title>
          <Sidebar onNavigate={() => onOpenChange(false)} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
