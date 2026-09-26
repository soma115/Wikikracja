// Profile page - notification and theme settings

window.wkOnReady(function() {
	const contactMethod = document.querySelector('[data-contact-method]');
	const contactLinkField = document.querySelector('[data-contact-link-field]');
	const phoneFields = document.querySelectorAll('[data-contact-phone-field]');
	const phoneCountry = document.querySelector('[data-phone-country]');
	const phoneInput = document.querySelector('[data-phone-input]');
	const businessToggle = document.querySelector('[data-business-toggle]');
	const businessFields = document.querySelectorAll('[data-business-fields]');

	function updateContactFields() {
		const method = contactMethod ? contactMethod.value : '';
		const needsLink = ['facebook', 'discord', 'telegram', 'signal'].includes(method);
		if (contactLinkField) {
			contactLinkField.classList.toggle('tw-d-none', !needsLink);
		}
		phoneFields.forEach(field => field.classList.toggle('tw-d-none', false));
	}

	if (contactMethod) {
		contactMethod.addEventListener('change', updateContactFields);
		updateContactFields();
	}

	if (phoneCountry && phoneInput) {
		let previousCountryCode = phoneCountry.options[phoneCountry.selectedIndex]?.textContent.match(/\+(\d+)/)?.[1] || '';
		phoneCountry.addEventListener('change', function() {
			const value = phoneInput.value.trim();
			if (previousCountryCode && value.startsWith(`+${previousCountryCode}`)) {
				phoneInput.value = value.slice(previousCountryCode.length + 1).trim();
			}
			previousCountryCode = this.options[this.selectedIndex]?.textContent.match(/\+(\d+)/)?.[1] || '';
		});
	}

	function updateBusinessFields() {
		businessFields.forEach(field => field.classList.toggle('tw-d-none', !businessToggle.checked));
	}

	if (businessToggle) {
		businessToggle.addEventListener('change', updateBusinessFields);
		updateBusinessFields();
	}

	const resourceSection = document.querySelector('[data-resource-section]');
	if (resourceSection) {
		const resourceName = resourceSection.querySelector('[data-resource-name]');
		const resourceKind = resourceSection.querySelector('[name="kind"]');
		const resourceSuggestions = resourceSection.querySelector('[data-resource-suggestions]');
		let searchTimer;

		const resourceKindRequired = resourceSection.dataset.resourceKindRequired !== 'false';

		function hideResourceSuggestions() {
			resourceSuggestions.replaceChildren();
			resourceSuggestions.classList.remove('tw-show');
		}

		function updateResourceSearchState() {
			resourceName.disabled = resourceKindRequired && !resourceKind.value;
			if (resourceKindRequired && !resourceKind.value) {
				hideResourceSuggestions();
			}
		}

		resourceKind.addEventListener('change', updateResourceSearchState);
		resourceName.addEventListener('input', function() {
			if (resourceKindRequired && !resourceKind.value) return;
			clearTimeout(searchTimer);
			searchTimer = setTimeout(() => {
				const params = new URLSearchParams({q: resourceName.value});
				if (resourceKind.value) params.set('kind', resourceKind.value);
				fetch(`${resourceSection.dataset.resourceSearchUrl}?${params}`)
					.then(response => response.json())
					.then(data => {
						resourceSuggestions.replaceChildren(...data.items.map(item => {
							const option = document.createElement('button');
							option.type = 'button';
							option.className = 'tw-dropdown-item tw-block tw-w-full tw-text-start';
							option.textContent = item.name;
							option.addEventListener('click', function() {
								resourceName.value = item.name;
								hideResourceSuggestions();
							});
							return option;
						}));
						resourceSuggestions.classList.toggle('tw-show', data.items.length > 0);
					})
					.catch(hideResourceSuggestions);
			}, 250);
		});

		updateResourceSearchState();
	}

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
