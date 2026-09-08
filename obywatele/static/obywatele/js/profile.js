// Profile page - notification and theme settings

document.addEventListener('DOMContentLoaded', function() {
	const toggles = document.querySelectorAll('[id^="toggle-"]');
	const frequencySelect = document.getElementById('email-frequency');
	const themeSwitcher = document.getElementById('theme-switcher');

	function sendSetting(url, body) {
		return window.apiFetch(url, { method: 'POST', body: body })
			.then(response => response.json());
	}

	toggles.forEach(toggle => {
		toggle.addEventListener('change', function() {
			const wasChecked = !this.checked;
			const isChecked = this.checked;

			sendSetting(this.dataset.url, { enabled: isChecked })
				.then(data => {
					if (!data.success) {
						this.checked = wasChecked;
					}
				})
				.catch(() => {
					this.checked = wasChecked;
				});
		});
	});

	if (frequencySelect) {
		const originalValue = frequencySelect.value;
		frequencySelect.addEventListener('change', function() {
			const newValue = this.value;

			sendSetting(this.dataset.url, { value: newValue })
				.then(data => {
					if (!data.success) {
						this.value = originalValue;
					}
				})
				.catch(() => {
					this.value = originalValue;
				});
		});
	}

	if (themeSwitcher) {
		const themeBtns = themeSwitcher.querySelectorAll('button[data-value]');
		const themeUrl = themeSwitcher.dataset.url;

		function updateThemeBtns(active) {
			themeBtns.forEach(function(btn) {
				if (btn.dataset.value === active) {
					btn.classList.remove('tw-btn-outline-secondary');
					btn.classList.add('tw-btn-primary');
				} else {
					btn.classList.remove('tw-btn-primary');
					btn.classList.add('tw-btn-outline-secondary');
				}
			});
		}

		function setTheme(value) {
			if (window.applyTheme) {
				window.applyTheme(value);
			}
			updateThemeBtns(value);
		}

		themeBtns.forEach(function(btn) {
			btn.addEventListener('click', function() {
				const value = this.dataset.value;
				const previous = themeSwitcher.dataset.currentTheme || themeSwitcher.dataset.initialTheme;
				themeSwitcher.dataset.currentTheme = value;
				setTheme(value);

				sendSetting(themeUrl, { value: value })
					.then(data => {
						if (!data.success) {
							themeSwitcher.dataset.currentTheme = previous;
							setTheme(previous);
						}
					})
					.catch(() => {
						themeSwitcher.dataset.currentTheme = previous;
						setTheme(previous);
					});
			});
		});

		// Apply the server-stored theme on page load so UI and email setting are consistent.
		const initialTheme = themeSwitcher.dataset.initialTheme || 'auto';
		themeSwitcher.dataset.currentTheme = initialTheme;
		setTheme(initialTheme);
	}
});
