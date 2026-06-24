"use client";

import { Button } from "@/components/ui/Button";
import { useCapture } from "./CaptureProvider";

export function CaptureButton() {
  const { open } = useCapture();
  return (
    <Button variant="primary" onClick={open}>
      ⊕ Capture
    </Button>
  );
}
