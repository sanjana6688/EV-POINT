/* Scroll Triggered Entrance Animations with Staggering - EV POINT */

document.addEventListener('DOMContentLoaded', () => {
  // Respect users' prefers-reduced-motion setting
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  // Inject CSS styles dynamically
  if (!document.getElementById('scroll-animation-styles')) {
    const style = document.createElement('style');
    style.id = 'scroll-animation-styles';
    style.innerHTML = `
      .scroll-reveal {
        opacity: 0 !important;
        transform: translateY(24px) scale(0.98) !important;
        transition: opacity 0.75s cubic-bezier(0.16, 1, 0.3, 1), 
                    transform 0.75s cubic-bezier(0.16, 1, 0.3, 1) !important;
        will-change: transform, opacity;
      }
      .scroll-reveal.revealed {
        opacity: 1 !important;
        transform: translateY(0) scale(1) !important;
      }
    `;
    document.head.appendChild(style);
  }

  // Select target elements to reveal on scroll
  const selector = [
    '.info-card',
    '.value-card',
    '.stat-card',
    '.service-card',
    '.card.rounded-card',
    '.about-card',
    '.booking-card',
    '.welcome-section',
    '.recent-activity',
    '.quick-actions'
  ].join(', ');

  const elements = document.querySelectorAll(selector);

  // Group elements by parent container to implement staggering
  const groups = new Map();
  elements.forEach(el => {
    el.classList.add('scroll-reveal');
    const parent = el.parentElement;
    if (!groups.has(parent)) {
      groups.set(parent, []);
    }
    groups.get(parent).push(el);
  });

  const observerOptions = {
    threshold: 0.05,
    rootMargin: '0px 0px -30px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const parent = entry.target;
        const groupElements = groups.get(parent);
        if (groupElements) {
          groupElements.forEach((el, index) => {
            setTimeout(() => {
              el.classList.add('revealed');
            }, index * 80); // Stagger delay of 80ms
          });
          observer.unobserve(parent);
        }
      }
    });
  }, observerOptions);

  groups.forEach((groupEls, parent) => {
    observer.observe(parent);
  });
});
