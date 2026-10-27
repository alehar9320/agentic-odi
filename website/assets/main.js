// vanilla JS for CTA interaction, copy buttons, and progressive enhancement
// No framework, no fetch, no external URLs

// Design system: respect prefers-reduced-motion
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

// Reveal-on-scroll with IntersectionObserver (opt-in, respects reduced motion)
document.addEventListener('DOMContentLoaded', () => {
  if ('IntersectionObserver' in window && !prefersReducedMotion.matches) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
            observer.disconnect();
          }
        });
      },
      { threshold: 0.15, rootMargin: '0px 0px -50px 0px' }
    );
    document.querySelectorAll('section[id]').forEach(section => {
      observer.observe(section);
    });
  }
});

// Copy button logic
document.addEventListener('DOMContentLoaded', () => {
  const copyButtons = document.querySelectorAll('.copy-btn');
  const liveRegion = document.createElement('span');
  liveRegion.setAttribute('aria-live', 'polite');
  liveRegion.setAttribute('role', 'status');
  document.body.appendChild(liveRegion);

  copyButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const codeEl = btn.previousElementSibling;
      if (codeEl && codeEl.tagName === 'CODE') {
        navigator.clipboard.writeText(codeEl.textContent).then(() => {
          btn.textContent = 'Copied';
          liveRegion.textContent = 'Copied to clipboard';
          setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
        });
      }
    });
  });
});

// Apply reduced-motion class to html element
if (prefersReducedMotion.matches) {
  document.documentElement.classList.add('reduced-motion');
}

// Listen for changes to prefers-reduced-motion
prefersReducedMotion.addEventListener('change', (e) => {
  if (e.matches) {
    document.documentElement.classList.add('reduced-motion');
  } else {
    document.documentElement.classList.remove('reduced-motion');
  }
});