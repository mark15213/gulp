type LogContext = Record<string, unknown>;

function serializeError(error: unknown): unknown {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: error.stack,
    };
  }
  return error;
}

export function logError(message: string, error: unknown, context: LogContext = {}): void {
  if (process.env.NODE_ENV === "test") return;
  console.error(`[gulp] ${message}`, {
    ...context,
    error: serializeError(error),
  });
}
