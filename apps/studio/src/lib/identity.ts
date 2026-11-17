import { useStudio } from "../state/StudioContext";

/**
 * Who is using this Studio (#736).
 *
 * There is no account directory in the product, so the only name is the one
 * Settings stores. `StudioBrief.role` is free-text context from the first-run
 * introduction ("I'm the PM for the deploy tool…"), not an account role, so it
 * is deliberately not used here: the chip labels the gap instead of printing a
 * sentence as a role.
 */
export const IDENTITY_ROLE_PLACEHOLDER = "Colleague — not set from your account";

export interface UserIdentity {
  name: string;
  initial: string;
  /** The account's role, when the product has one. Today it never does. */
  role: string | null;
}

/**
 * Pure, so the fallbacks are provable without a renderer. A name with no
 * letters still gets one visible initial rather than an empty chip.
 */
export function identityFor(displayName: string): UserIdentity {
  const name = displayName.trim() || "You";
  return {
    name,
    initial: Array.from(name)[0]?.toUpperCase() ?? "Y",
    role: null,
  };
}

/** `name` and `initial` come from `displayName`; `role` is the honest gap. */
export function useUserIdentity(): UserIdentity {
  const { displayName } = useStudio();
  return identityFor(displayName);
}
