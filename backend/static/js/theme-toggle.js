// backend/static/js/theme-toggle.js
(function() {
  const THEME_KEY = 'themePreference';
  const LIGHT_THEME = 'light';
  const DARK_THEME = 'dark';
  const themeToggleBtn = document.getElementById('theme-toggle-btn');

  // SVG icons - ensure these are correctly escaped if needed within a JS string, though SVGs are usually fine.
  const sunIcon = '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm0 13a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zm8-5a1 1 0 01-.293.707l-.002.002A1 1 0 0017 12a1 1 0 00.002.001L17 12l.002.001.002.001a1 1 0 000 1.998h-1a1 1 0 100 2h1a1 1 0 000-1.998l.002-.001.002-.001A1 1 0 0017.707 13H18a1 1 0 010-2h-.293A1 1 0 0118 10zm-14 0a1 1 0 01-.293.707l-.002.002A1 1 0 001 12a1 1 0 00.002.001L1 12l.002.001.002.001a1 1 0 000 1.998H0a1 1 0 100 2h1a1 1 0 000-1.998l.002-.001.002-.001A1 1 0 001.707 13H2a1 1 0 010-2h-.293A1 1 0 012 10zm6.293-6.293A1 1 0 017.707 3L7 3.707a1 1 0 00-1.414 1.414L6.293 7A1 1 0 017 7.707l.002-.001A1 1 0 017.707 7l-.002-.001A1 1 0 017 6.293zm5.414 0A1 1 0 0113 3.707l.002-.001A1 1 0 0113.707 3l.001.002A1 1 0 0113 4.707L12.293 7A1 1 0 0111.293 7l-.001.002A1 1 0 0111 6.293l.002.001zm-2.586 7.586A3.502 3.502 0 0010.5 10c0-1.933 1.567-3.5 3.5-3.5a3.502 3.502 0 002.586 5.914zM10 14a4 4 0 100-8 4 4 0 000 8z"></path></svg>'; // Sun icon
  const moonIcon = '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"></path></svg>';   // Moon icon

  function getPreferredTheme() {
    const storedTheme = localStorage.getItem(THEME_KEY);
    if (storedTheme) {
      return storedTheme;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK_THEME : LIGHT_THEME;
  }

  function applyTheme(theme) {
    if (theme === DARK_THEME) {
      document.documentElement.setAttribute('data-theme', DARK_THEME);
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
      document.documentElement.classList.remove('dark');
    }

    if (themeToggleBtn) {
        themeToggleBtn.innerHTML = theme === DARK_THEME ? sunIcon : moonIcon;
    }
  }

  function toggleTheme() {
    let currentTheme = LIGHT_THEME;
    // Check data-theme attribute first
    if (document.documentElement.hasAttribute('data-theme') && document.documentElement.getAttribute('data-theme') === DARK_THEME) {
        currentTheme = DARK_THEME;
    }
    // Fallback to checking class if data-theme is not used consistently (though it should be)
    else if (document.documentElement.classList.contains('dark')) {
        currentTheme = DARK_THEME;
    }

    const newTheme = currentTheme === DARK_THEME ? LIGHT_THEME : DARK_THEME;
    localStorage.setItem(THEME_KEY, newTheme);
    applyTheme(newTheme);
  }

  // Apply theme on initial load
  const initialTheme = getPreferredTheme();
  applyTheme(initialTheme);

  // Add event listener to the toggle button
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', toggleTheme);
  } else {
    // Fallback for debugging or if button is not critical
    window.toggleTheme = toggleTheme;
    console.log("Theme toggle button with id 'theme-toggle-btn' not found. 'window.toggleTheme()' is available for manual calls.");
  }
})();
