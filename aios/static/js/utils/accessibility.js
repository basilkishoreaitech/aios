/**
 * SRE Accessibility utilities for screen readers and keyboard navigation.
 */

function toggleContrastMode() {
  document.body.classList.toggle('high-contrast');
  const isHigh = document.body.classList.contains('high-contrast');
  localStorage.setItem('a11y_contrast', isHigh ? 'true' : 'false');
  logger.info(`Accessibility contrast set: ${isHigh}`);
}

function initAccessibilitySettings() {
  const contrast = localStorage.getItem('a11y_contrast');
  if (contrast === 'true') {
    document.body.classList.add('high-contrast');
  }

  // Keyboard trap for SRE focus control
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      document.body.classList.add('user-is-tabbing');
    }
  });
}

// Global logger helper for SRE console notifications
const logger = {
  info: (msg) => console.log(`[AIOS-UI] INFO: ${msg}`),
  error: (msg) => console.error(`[AIOS-UI] ERROR: ${msg}`)
};
