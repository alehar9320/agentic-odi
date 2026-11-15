// Hover-card primitive: a focusable trigger that reveals its content in a
// portal when hovered, focused, or activated with Enter/Space, and closes on
// Escape (returning focus to the trigger) or blur.
//
// Authored locally as a reusable presentation primitive for the claim-citation
// surface; no upstream artefact was fetched in this environment, so it is
// tracked as first-party in vendor.lock.json rather than as a copy-in.
import * as React from "react"
import { createPortal } from "react-dom"

export function HoverCard({
  children,
  content,
  className,
}: {
  children: React.ReactNode
  content: React.ReactNode
  className?: string
}) {
  const [open, setOpen] = React.useState(false)
  const trigger = React.useRef<HTMLElement | null>(null)
  // Set while Escape moves focus back to the trigger, so the focus event the
  // move produces does not reopen the card the Escape just closed.
  const returningFocus = React.useRef(false)

  const openCard = () => setOpen(true)
  const closeCard = () => setOpen(false)

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      setOpen(true)
    } else if (event.key === "Escape") {
      returningFocus.current = true
      setOpen(false)
      trigger.current?.focus()
    }
  }

  const onFocus = () => {
    if (returningFocus.current) {
      returningFocus.current = false
      return
    }
    setOpen(true)
  }

  return (
    <>
      <span
        ref={trigger}
        tabIndex={0}
        className={className}
        onMouseEnter={openCard}
        onMouseLeave={closeCard}
        onFocus={onFocus}
        onBlur={closeCard}
        onKeyDown={onKeyDown}
      >
        {children}
      </span>
      {open && createPortal(<div className="hover-card__content">{content}</div>, document.body)}
    </>
  )
}
