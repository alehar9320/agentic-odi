/**
 * The model picker in the composer's hint row.
 *
 * The list comes from the sidecar because the model server may only be
 * reachable from the host machine and is not necessarily CORS-open. Choosing a
 * model is the same write as the Settings field, so both stay in sync through
 * `StudioContext.saveSettings`.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { fetchModels } from "../../api/studioApi";
import { useStudio } from "../../state/StudioContext";
import { ChevronDownIcon } from "../icons";

export function ModelPicker() {
  const { settings, saveSettings, llmHealth, openPanel } = useStudio();
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const [announcement, setAnnouncement] = useState("");

  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<(HTMLButtonElement | null)[]>([]);
  // One probe per backend+key, not one per open: reopening a menu the user has
  // already seen must not hit the model server again.
  const loadedFor = useRef<string | null>(null);
  const cacheKey = `${settings.base_url}\u0000${settings.api_key}`;

  // The reported list may not mention the model that is actually configured, so
  // the current one is always offered rather than silently disappearing.
  const options = useMemo(() => {
    // An empty answer is not a list to decorate: it means the backend told us
    // nothing, and offering only the configured name would hide that.
    if (!models?.length) {
      return [];
    }
    if (!settings.model_name || models.includes(settings.model_name)) {
      return models;
    }
    return [settings.model_name, ...models];
  }, [models, settings.model_name]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const requestedFor = cacheKey;
    if (loadedFor.current === requestedFor) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    void fetchModels({ base_url: settings.base_url, api_key: settings.api_key })
      .then((result) => {
        if (cancelled) {
          return;
        }
        loadedFor.current = requestedFor;
        setModels(result.models);
        setError(result.error);
        // The list arrives after the menu opened, so the keyboard cursor is
        // still on the first row. Put it on the model in use instead, where the
        // reader expects to start.
        if (result.models.length > 0) {
          const listed = result.models.includes(settings.model_name)
            ? result.models
            : [settings.model_name, ...result.models];
          setActive(Math.max(listed.indexOf(settings.model_name), 0));
        }
      })
      .catch((failure: unknown) => {
        if (cancelled) {
          return;
        }
        setModels([]);
        setError(
          failure instanceof Error ? failure.message : "Could not reach the model server.",
        );
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [open, cacheKey, settings.base_url, settings.api_key, settings.model_name]);

  // Clicking anywhere else is a dismissal, not a selection.
  useEffect(() => {
    if (!open) {
      return;
    }
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // Move focus onto the current option when the list appears, so a keyboard
  // user lands inside it instead of having to Tab from the trigger.
  useEffect(() => {
    if (!open || options.length === 0) {
      return;
    }
    optionRefs.current[active]?.focus();
  }, [open, active, options.length]);

  function openMenu(position: "selected" | "last") {
    removeErrorToRetry();
    const selected = Math.max(options.indexOf(settings.model_name), 0);
    setActive(position === "last" ? Math.max(options.length - 1, 0) : selected);
    setOpen(true);
  }

  // A previous failure must not make reopening look cached.
  function removeErrorToRetry() {
    if (loadedFor.current !== null && error) {
      loadedFor.current = null;
    }
  }

  function choose(model: string) {
    if (model !== settings.model_name) {
      saveSettings({ ...settings, model_name: model });
      setAnnouncement(`Model set to ${model}`);
    }
    setOpen(false);
    triggerRef.current?.focus();
  }

  function onMenuKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
      return;
    }
    if (event.key === "Tab") {
      setOpen(false);
      return;
    }
    // With no options the menu holds plain content (the explanation and its
    // Settings button); those keys belong to whatever has focus there.
    if (options.length === 0) {
      return;
    }

    switch (event.key) {
      case "ArrowDown":
      case "ArrowUp": {
        event.preventDefault();
        const delta = event.key === "ArrowDown" ? 1 : -1;
        setActive((index) => (index + delta + options.length) % options.length);
        return;
      }
      case "Home":
        event.preventDefault();
        setActive(0);
        return;
      case "End":
        event.preventDefault();
        setActive(Math.max(options.length - 1, 0));
        return;
      case "Enter":
      case " ": {
        const model = options[active];
        if (model) {
          event.preventDefault();
          choose(model);
        }
        return;
      }
      default:
        return;
    }
  }

  const offline = llmHealth.healthy === false;

  return (
    <div className="model-picker" ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className={`model-picker__trigger${offline ? " is-offline" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`${offline ? "Model server offline. " : ""}Model: ${
          settings.model_name || "none configured"
        }. Choose a model`}
        title={offline ? "Model server offline — the last choice is still shown" : settings.model_name}
        onClick={() => (open ? setOpen(false) : openMenu("selected"))}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            openMenu(event.key === "ArrowDown" ? "selected" : "last");
          }
          if (event.key === "Escape" && open) {
            event.preventDefault();
            setOpen(false);
          }
        }}
      >
        <span className="model-picker__label">Model</span>
        <span className="model-picker__value">{settings.model_name || "Not set"}</span>
        <ChevronDownIcon size={13} />
      </button>

      {open ? (
        <div className="model-picker__menu" onKeyDown={onMenuKeyDown}>
          {loading ? (
            <p className="model-picker__state" role="status">
              Looking for models…
            </p>
          ) : options.length > 0 ? (
            <>
              {/* Only options live inside the listbox; a note beside it would
                  be read as an item. */}
              <div role="listbox" aria-label="Choose a model">
                {options.map((model, index) => {
                  const selected = model === settings.model_name;
                  return (
                    <button
                      key={model}
                      ref={(element) => {
                        optionRefs.current[index] = element;
                      }}
                      type="button"
                      role="option"
                      aria-selected={selected}
                      tabIndex={index === active ? 0 : -1}
                      className={`model-picker__option${selected ? " is-selected" : ""}`}
                      onClick={() => choose(model)}
                    >
                      <span className="model-picker__option-name">{model}</span>
                      {selected ? <span className="model-picker__check">Current</span> : null}
                    </button>
                  );
                })}
              </div>
              {error ? <p className="model-picker__note">{error}</p> : null}
            </>
          ) : (
            <div className="model-picker__state" role="status">
              <p>{error ?? "The model server reported no models."}</p>
              <button
                type="button"
                className="quiet-action"
                onClick={() => {
                  setOpen(false);
                  openPanel("settings");
                }}
              >
                Model settings
              </button>
            </div>
          )}
        </div>
      ) : null}

      <span className="sr-only" role="status">
        {announcement}
      </span>
    </div>
  );
}
