// Profile page - notification settings

document.addEventListener('DOMContentLoaded', function() {
	const toggles = document.querySelectorAll('[id^="toggle-"]');
	const frequencySelect = document.getElementById('email-frequency');

	function getCookie(name) {
		const value = `; ${document.cookie}`;
		const parts = value.split(`; ${name}=`);
		if (parts.length === 2) return parts.pop().split(';').shift();
	}

	function sendSetting(url, body) {
		return fetch(url, {
			method: 'POST',
			headers: {
				'X-CSRFToken': getCookie('csrftoken'),
				'Content-Type': 'application/json',
			},
			body: JSON.stringify(body)
		}).then(response => response.json());
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
});
