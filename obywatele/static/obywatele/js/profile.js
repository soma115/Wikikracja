// Profile page - email notification toggles

document.addEventListener('DOMContentLoaded', function() {
	const toggles = document.querySelectorAll('[id^="toggle-"]');

	function getCookie(name) {
		const value = `; ${document.cookie}`;
		const parts = value.split(`; ${name}=`);
		if (parts.length === 2) return parts.pop().split(';').shift();
	}

	toggles.forEach(toggle => {
		toggle.addEventListener('change', function() {
			const wasChecked = !this.checked;
			const isChecked = this.checked;

			fetch(this.dataset.url, {
				method: 'POST',
				headers: {
					'X-CSRFToken': getCookie('csrftoken'),
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({ enabled: isChecked })
			})
				.then(response => response.json())
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
});
