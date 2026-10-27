/* eslint-disable react-refresh/only-export-components -- the provider and its hooks intentionally share one module */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { createUpdateService, type UpdateService } from "./service";
import { createDesktopTransport } from "./transport";
import type { UpdateSnapshot } from "./types";

const UpdateContext = createContext<UpdateService | null>(null);

function createDefaultService(): UpdateService {
  const transport = createDesktopTransport();
  return createUpdateService({
    transport: {
      ...transport,
      // `tauri dev` serves the Vite dev build; there is no installed bundle for
      // the updater to replace, so say so instead of reporting a failed check.
      supported: () => transport.supported() && !import.meta.env.DEV,
    },
  });
}

interface UpdateProviderProps {
  children: ReactNode;
  /** Injected by tests; the app creates one desktop-backed service. */
  service?: UpdateService;
}

export function UpdateProvider({ children, service }: UpdateProviderProps) {
  const [instance] = useState(() => service ?? createDefaultService());

  useEffect(() => {
    instance.start();
    return () => instance.stop();
  }, [instance]);

  return <UpdateContext.Provider value={instance}>{children}</UpdateContext.Provider>;
}

export function useUpdateService(): UpdateService {
  const service = useContext(UpdateContext);
  if (!service) {
    throw new Error("useUpdateService must be used within an UpdateProvider");
  }
  return service;
}

/** The single source of truth for every update surface in the shell. */
export function useUpdateSnapshot(): UpdateSnapshot {
  const service = useUpdateService();
  return useSyncExternalStore(service.subscribe, service.getSnapshot, service.getSnapshot);
}
