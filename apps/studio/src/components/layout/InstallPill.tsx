/* eslint-disable react-refresh/only-export-components -- the provider and its hook intentionally share one module */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import {
  createInstallController,
  type InstallController,
  type InstallSnapshot,
} from "../../install";
import { DownloadIcon } from "../icons";

const InstallContext = createContext<InstallController | null>(null);

interface InstallProviderProps {
  children: ReactNode;
  /** Injected by tests; the app creates one window-backed controller. */
  controller?: InstallController;
}

export function InstallProvider({ children, controller }: InstallProviderProps) {
  const [instance] = useState(() => controller ?? createInstallController());

  useEffect(() => () => instance.dispose(), [instance]);

  return <InstallContext.Provider value={instance}>{children}</InstallContext.Provider>;
}

export function useInstallController(): InstallController {
  const controller = useContext(InstallContext);
  if (!controller) {
    throw new Error("useInstallController must be used within an InstallProvider");
  }
  return controller;
}

/** The single source of truth for whether the install offer can be made. */
export function useInstallSnapshot(): InstallSnapshot {
  const controller = useInstallController();
  return useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    controller.getSnapshot,
  );
}

/**
 * One quiet pill in the bar, and only when the browser has a prompt to give.
 *
 * It is absent when the app is already installed, when the browser has not
 * offered an install prompt, and after a dismissal. It never prompts on its own.
 */
export function InstallPill() {
  const controller = useInstallController();
  const { canInstall } = useInstallSnapshot();

  if (!canInstall) {
    return null;
  }

  return (
    <button
      type="button"
      className="studio-pill pill-install"
      onClick={() => void controller.prompt()}
      aria-label="Install the Studio as an app"
      title="Install the Studio as an app"
    >
      <DownloadIcon size={15} />
      Install
    </button>
  );
}
